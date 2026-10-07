#!/usr/bin/env bash
set -euo pipefail
source_script=$1
for scenario in build-failure success restart-failure; do
  sandbox=$(mktemp -d /tmp/alca-deploy-test.XXXXXX)
  root="$sandbox/alca-financas"
  mkdir -p "$root/build/frontend" "$sandbox/bin"
  cd "$root"
  git init -q
  git config user.email synthetic@example.invalid
  git config user.name Synthetic
  printf old > build/frontend/index.html
  printf old-asset > build/frontend/old.js
  printf nginx > nginx.conf
  printf compose > docker-compose.prod.yml
  printf original > marker
  git add nginx.conf docker-compose.prod.yml marker
  git commit -qm old
  before=$(git rev-parse HEAD)
  printf new > marker
  git commit -qam new
  target=$(git rev-parse HEAD)
  git switch -q --detach "$before"
  mkdir -p "$sandbox/alca-releases"
  sed "s|/apps/|$sandbox/|g" "$source_script" > "$sandbox/deploy.sh"
  cat > "$sandbox/bin/docker" <<'MOCK'
#!/usr/bin/env bash
if [[ "$*" == *"npm ci"* ]]; then
  [ "$SCENARIO" != build-failure ] || exit 17
  for arg in "$@"; do
    if [[ "$arg" == *frontend:/app ]]; then
      app=${arg%:/app}
      mkdir -p "$app/dist"
      printf new > "$app/dist/index.html"
    fi
  done
fi
if [[ "$*" == *'up -d'* ]] && [ "$SCENARIO" = restart-failure ] && [ ! -f "$MOCK_MARKER" ]; then
  touch "$MOCK_MARKER"
  exit 18
fi
exit 0
MOCK
  cat > "$sandbox/bin/curl" <<'MOCK'
#!/usr/bin/env bash
if [[ "$*" == *release.txt* ]]; then printf '%s\n' "$TARGET_SHA"; fi
MOCK
  chmod +x "$sandbox/bin/"*
  export PATH="$sandbox/bin:$PATH" SCENARIO="$scenario" TARGET_SHA="$target" MOCK_MARKER="$sandbox/restart-marker"
  export VITE_SUPABASE_URL=http://synthetic.invalid VITE_SUPABASE_ANON_KEY=synthetic
  set +e
  bash "$sandbox/deploy.sh" "$target" > "$sandbox/result.log" 2>&1
  result=$?
  set -e
  if [ "$scenario" = success ]; then
    test "$result" -eq 0
    test "$(cat build/frontend/index.html)" = new
    test "$(cat build/frontend/old.js)" = old-asset
    test "$(git rev-parse HEAD)" = "$target"
  else
    test "$result" -ne 0
    test "$(cat build/frontend/index.html)" = old
    test "$(git rev-parse HEAD)" = "$before"
    test "$(cat nginx.conf)" = nginx
  fi
  echo "PASS: $scenario (isolated synthetic sandbox)"
done
MOCK_UNUSED=1