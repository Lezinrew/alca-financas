#!/usr/bin/env bash
# Build in a disposable checkout. Keep the live artifact until validation passes.
set -euo pipefail
root=/apps/alca-financas
sha=${1:?usage: deploy-frontend-atomic.sh COMMIT_SHA}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
: "${VITE_SUPABASE_URL:?missing public build configuration}"
: "${VITE_SUPABASE_ANON_KEY:?missing public build configuration}"
cd "$root"
test -z "$(git status --porcelain --untracked-files=no)" || { echo 'Tracked server changes: deployment stopped'; exit 1; }
old_sha=$(git rev-parse HEAD)
docker compose -f docker-compose.prod.yml config -q
stamp="${sha}-$(date -u +%Y%m%dT%H%M%SZ)"
release="/apps/alca-releases/$stamp"
backup="/apps/alca-backups/$stamp"
stage="$root/build/frontend-stage-$stamp"
previous="$root/build/frontend-before-$stamp"
umask 077
mkdir -p "$backup"
tar -czf "$backup/frontend-before.tar.gz" build/frontend nginx.conf docker-compose.prod.yml
cp nginx.conf "$backup/nginx.conf"
git worktree add --detach "$release" "$sha"
docker run --rm -e VITE_SUPABASE_URL -e VITE_SUPABASE_ANON_KEY \
  -v "$release/frontend:/app" -w /app node:22-alpine sh -lc 'npm ci && npm run build'
test -s "$release/frontend/dist/index.html"
mkdir -p "$stage"
# Retain old hashed assets for tabs that were open during the deployment.
cp -a build/frontend/. "$stage/"
cp -a "$release/frontend/dist/." "$stage/"
printf '%s\n' "$sha" > "$stage/release.txt"
chmod -R a+rX "$stage"
docker run --rm --network alca-financas_alca-network \
  -v "$release/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$stage:/usr/share/nginx/html:ro" nginx:alpine nginx -t
switched=0
swapped=0
rollback() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$switched" -eq 1 ]; then
    if [ "$swapped" -eq 1 ]; then
      if [ -d "$root/build/frontend" ]; then
        mv "$root/build/frontend" "$stage-failed"
      fi
      mv "$previous" "$root/build/frontend"
    fi
    git switch --detach "$old_sha"
    cat "$backup/nginx.conf" > "$root/nginx.conf"
    docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate frontend
    echo "Rolled back frontend; backup: $backup"
  fi
  exit "$status"
}
trap rollback EXIT
git switch --detach "$sha"
switched=1
docker compose -f docker-compose.prod.yml config -q
mv build/frontend "$previous"
swapped=1
mv "$stage" build/frontend
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate frontend
docker compose -f docker-compose.prod.yml exec -T frontend nginx -t
curl --fail --silent --show-error http://127.0.0.1:3000/release.txt | grep -Fx "$sha"
curl --fail --silent --show-error http://127.0.0.1:8001/api/health > /dev/null
trap - EXIT
echo "Frontend published: $sha; backup: $backup"
