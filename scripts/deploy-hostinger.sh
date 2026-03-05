#!/bin/bash
###############################################################################
# Deploy Hostinger - Alça Finanças
# Script para deploy no servidor via Docker Compose
# Assume que a infraestrutura Docker já está configurada
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações
PROJECT_DIR="/var/www/alca-financas"
SERVICE_NAME="alca-financas"
COMPOSE_FILE="docker-compose.prod.yml"

echo -e "${BLUE}🚀 Deploy Hostinger - Alça Finanças${NC}"
echo ""

# Verificar se está no diretório correto
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Diretório do projeto não encontrado: ${PROJECT_DIR}${NC}"
    echo "Execute o script de setup inicial primeiro: deploy-docker-remote.sh"
    exit 1
fi

cd "$PROJECT_DIR"

# 1. Atualizar código
echo -e "${BLUE}📥 Atualizando código do repositório...${NC}"
if [ -d ".git" ]; then
    git fetch origin
    git reset --hard origin/main
else
    echo -e "${RED}❌ Diretório não é um repositório Git${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Código atualizado${NC}"
echo ""

# 2. Verificar arquivo .env
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado!${NC}"
    echo "Crie o arquivo .env com suas credenciais Supabase."
    echo "Veja o guia em docs/DEPLOY-GUIDE.md"
    exit 1
fi
echo -e "${GREEN}✅ Arquivo .env encontrado${NC}"
echo ""

# 3. Build do frontend
echo -e "${BLUE}🎨 Buildando frontend...${NC}"
mkdir -p build/frontend
docker run --rm \
    -v "$(pwd)/frontend:/app" \
    -v "$(pwd)/build/frontend:/app/dist" \
    -w /app \
    --env-file .env \
    node:20-alpine \
    sh -c 'npm ci && npm run build && cp -r dist/* /app/dist/'
echo -e "${GREEN}✅ Frontend buildado${NC}"
echo ""

# 4. Build das imagens Docker
echo -e "${BLUE}🏗️  Construindo imagens Docker...${NC}"
docker-compose -f "$COMPOSE_FILE" build
echo -e "${GREEN}✅ Imagens construídas${NC}"
echo ""

# 5. Parar containers antigos
echo -e "${BLUE}🛑 Parando containers antigos...${NC}"
docker-compose -f "$COMPOSE_FILE" down
echo ""

# 6. Iniciar containers
echo -e "${BLUE}🚀 Iniciando containers...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d
echo -e "${GREEN}✅ Containers iniciados${NC}"
echo ""

# 7. Aguardar inicialização
echo -e "${BLUE}⏳ Aguardando serviços iniciarem...${NC}"
sleep 5

# 8. Verificar status
echo -e "${BLUE}🔍 Verificando status...${NC}"
BACKEND_STATUS=$(docker-compose -f "$COMPOSE_FILE" ps backend | grep -c 'Up' || echo '0')
FRONTEND_STATUS=$(docker-compose -f "$COMPOSE_FILE" ps frontend | grep -c 'Up' || echo '0')

if [ "$BACKEND_STATUS" = "1" ] && [ "$FRONTEND_STATUS" = "1" ]; then
    echo -e "${GREEN}✅ Todos os containers estão rodando!${NC}"
else
    echo -e "${YELLOW}⚠️  Alguns containers podem não estar rodando corretamente${NC}"
    docker-compose -f "$COMPOSE_FILE" ps
fi
echo ""

# 9. Health check
echo -e "${BLUE}🏥 Testando health check...${NC}"
sleep 3
if curl -s http://localhost:8001/api/health | grep -q 'ok'; then
    echo -e "${GREEN}✅ Backend respondendo corretamente!${NC}"
else
    echo -e "${YELLOW}⚠️  Backend pode não estar respondendo. Verifique os logs.${NC}"
fi
echo ""

# 10. Resumo
echo -e "${GREEN}✅ Deploy concluído!${NC}"
echo ""
echo -e "${BLUE}📊 Status dos serviços:${NC}"
docker-compose -f "$COMPOSE_FILE" ps
echo ""
echo -e "${BLUE}📝 Comandos úteis:${NC}"
echo "  Ver logs backend:  docker-compose -f $COMPOSE_FILE logs -f backend"
echo "  Ver logs frontend: docker-compose -f $COMPOSE_FILE logs -f frontend"
echo "  Ver todos os logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "  Restart:           docker-compose -f $COMPOSE_FILE restart"
echo "  Parar:             docker-compose -f $COMPOSE_FILE down"
echo ""
