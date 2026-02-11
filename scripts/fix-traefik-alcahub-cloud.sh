#!/usr/bin/env bash
# =============================================================================
# Correção Traefik: alcahub.cloud → frontend, api.alcahub.cloud → backend,
#                   traefik.alcahub.cloud → dashboard Traefik
# Execute no VPS: ssh root@76.13.239.220
# =============================================================================
set -e

COMPOSE_DIR="/docker/n8n"
BACKUP_DIR="/root/traefik-backup-$(date +%Y%m%d-%H%M%S)"
# Gateway do Docker para acessar o host (Linux)
HOST_GW="172.17.0.1"
# Portas (ajuste se no seu VPS forem outras)
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-8001}"

echo "=== [1/7] Detectando portas do frontend e backend ==="
echo "Frontend (esperado ${FRONTEND_PORT}):"
ss -tlnp | grep -E ":${FRONTEND_PORT}|:80 " || true
echo "Backend (esperado ${BACKEND_PORT}):"
ss -tlnp | grep ":${BACKEND_PORT}" || true
echo ""
read -p "Frontend está na porta ${FRONTEND_PORT}? (s/n): " ok
[[ "$ok" != "s" ]] && read -p "Digite a porta do frontend: " FRONTEND_PORT
read -p "Backend está na porta ${BACKEND_PORT}? (s/n): " ok
[[ "$ok" != "s" ]] && read -p "Digite a porta do backend: " BACKEND_PORT
echo "Usando: Frontend=${FRONTEND_PORT}, Backend=${BACKEND_PORT}"
echo ""

echo "=== [2/7] Backup e visualização do docker-compose ==="
mkdir -p "$BACKUP_DIR"
cp "$COMPOSE_DIR/docker-compose.yml" "$BACKUP_DIR/"
echo "Backup em: $BACKUP_DIR"
cat "$COMPOSE_DIR/docker-compose.yml"
echo ""

echo "=== [3/7] Criando arquivo de configuração dinâmica do Traefik ==="
mkdir -p "$COMPOSE_DIR/traefik-dynamic"
cat > "$COMPOSE_DIR/traefik-dynamic/dynamic.yml" << 'DYNAMIC'
http:
  routers:
    alcahub-frontend:
      rule: "Host(`alcahub.cloud`) || Host(`www.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: alcahub-frontend
      priority: 100
    alcahub-api:
      rule: "Host(`api.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: alcahub-api
      priority: 100
    traefik-dashboard:
      rule: "Host(`traefik.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: api@internal
      priority: 1
  services:
    alcahub-frontend:
      loadBalancer:
        servers:
          - url: "http://HOST_GW:FRONTEND_PORT"
        passHostHeader: true
    alcahub-api:
      loadBalancer:
        servers:
          - url: "http://HOST_GW:BACKEND_PORT"
        passHostHeader: true
DYNAMIC

# Substituir placeholders
sed -i "s|HOST_GW|$HOST_GW|g" "$COMPOSE_DIR/traefik-dynamic/dynamic.yml"
sed -i "s|FRONTEND_PORT|$FRONTEND_PORT|g" "$COMPOSE_DIR/traefik-dynamic/dynamic.yml"
sed -i "s|BACKEND_PORT|$BACKEND_PORT|g" "$COMPOSE_DIR/traefik-dynamic/dynamic.yml"

echo "Arquivo criado: $COMPOSE_DIR/traefik-dynamic/dynamic.yml"
cat "$COMPOSE_DIR/traefik-dynamic/dynamic.yml"
echo ""

echo "=== [4/7] Desabilitando dashboard na raiz (se necessário) ==="
echo "É preciso editar o docker-compose.yml para:"
echo "  1. Adicionar --api.dashboard=false OU"
echo "  2. Garantir que o dashboard só responda em traefik.alcahub.cloud"
echo ""
echo "Adicionando provider de arquivo ao Traefik..."
echo ""

echo "=== [5/7] Aplicando patch no docker-compose do Traefik ==="
# Lê o compose atual e adiciona volumes e providers
if ! grep -q "traefik-dynamic" "$COMPOSE_DIR/docker-compose.yml"; then
  # Adiciona volume e arguments ao serviço traefik
  # Estrutura típica do n8n+traefik - ajuste conforme seu compose
  echo "ATENÇÃO: Edite manualmente $COMPOSE_DIR/docker-compose.yml e adicione:"
  echo ""
  echo "No serviço traefik, adicione ao 'command' ou 'args':"
  echo "  --providers.file.directory=/etc/traefik/dynamic"
  echo "  --providers.file.watch=true"
  echo "  --api.dashboard=false"
  echo ""
  echo "E acrescente nos volumes do traefik:"
  echo "  - $COMPOSE_DIR/traefik-dynamic:/etc/traefik/dynamic:ro"
  echo ""
  echo "Alternativa: se quiser manter o dashboard em traefik.alcahub.cloud,"
  echo "NÃO use --api.dashboard=false, apenas adicione o provider e o volume."
  echo ""
  read -p "Pressione Enter após editar o docker-compose..."
else
  echo "Volume traefik-dynamic já presente."
fi
echo ""

echo "=== [6/7] Reiniciando Traefik ==="
cd "$COMPOSE_DIR"
docker compose down traefik 2>/dev/null || docker-compose stop traefik 2>/dev/null || true
docker compose up -d traefik 2>/dev/null || docker-compose up -d traefik 2>/dev/null || true
echo "Aguardando 5 segundos..."
sleep 5
echo ""

echo "=== [7/7] Testes ==="
echo "Frontend (deve retornar HTML do app):"
curl -sk -o /dev/null -w "%{http_code}" "https://alcahub.cloud" && echo " OK" || echo " FALHOU"
echo "API (deve retornar {\"status\":\"ok\"}):"
curl -sk "https://api.alcahub.cloud/api/health" | head -c 100
echo ""
echo "Dashboard Traefik (traefik.alcahub.cloud - certifique-se de criar DNS A):"
curl -sk -o /dev/null -w "%{http_code}" "https://traefik.alcahub.cloud" 2>/dev/null && echo " OK" || echo " (criar DNS A para traefik.alcahub.cloud)"
echo ""
echo "=== Concluído ==="
echo "DNS: adicione registro A para traefik.alcahub.cloud -> 76.13.239.220"
echo "Teste no navegador: https://alcahub.cloud (deve mostrar o app Alca Finanças)"
