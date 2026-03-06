#!/bin/bash
# ============================================
# Deploy Script - Produção Profissional
# ============================================

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Alça Finanças - Deploy Profissional  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Verificar se está executando como root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Este script deve ser executado como root${NC}"
    echo "Execute: sudo bash deploy-production.sh"
    exit 1
fi

# Verificar se Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado${NC}"
    echo "Instale o Docker primeiro: apt install docker.io docker-compose-plugin"
    exit 1
fi

# Verificar se está no diretório correto
if [ ! -f "docker-compose.production.yml" ]; then
    echo -e "${RED}❌ Arquivo docker-compose.production.yml não encontrado${NC}"
    echo "Execute este script do diretório raiz do projeto"
    exit 1
fi

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado${NC}"
    echo "Criando .env a partir do exemplo..."
    cp .env.production.example .env
    echo -e "${YELLOW}⚠️  Configure o arquivo .env antes de continuar!${NC}"
    exit 1
fi

# Menu de opções
echo -e "${BLUE}Selecione uma opção:${NC}"
echo "1) Deploy inicial (primeira vez)"
echo "2) Atualizar aplicação (rebuild + restart)"
echo "3) Restart serviços"
echo "4) Ver logs"
echo "5) Backup"
echo "6) Status dos containers"
echo "7) Sair"
echo ""
read -p "Opção: " option

case $option in
    1)
        echo -e "${GREEN}🚀 Iniciando deploy inicial...${NC}"

        # Pull da imagem base
        echo -e "${BLUE}📥 Baixando imagens base...${NC}"
        docker compose -f docker-compose.production.yml pull

        # Build das imagens
        echo -e "${BLUE}🔨 Buildando imagens...${NC}"
        docker compose -f docker-compose.production.yml build --no-cache

        # Iniciar serviços
        echo -e "${BLUE}🚀 Iniciando serviços...${NC}"
        docker compose -f docker-compose.production.yml up -d

        # Aguardar inicialização
        echo -e "${BLUE}⏳ Aguardando inicialização (30s)...${NC}"
        sleep 30

        # Verificar status
        echo -e "${BLUE}✅ Status dos serviços:${NC}"
        docker compose -f docker-compose.production.yml ps

        # Health checks
        echo -e "${BLUE}🏥 Verificando health checks...${NC}"
        sleep 5

        echo -e "${BLUE}Backend:${NC}"
        curl -f http://localhost:8001/api/health || echo -e "${RED}❌ Backend não respondeu${NC}"

        echo -e "${BLUE}Frontend:${NC}"
        curl -f http://localhost:3000/ || echo -e "${RED}❌ Frontend não respondeu${NC}"

        echo ""
        echo -e "${GREEN}✅ Deploy inicial concluído!${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  Próximos passos:${NC}"
        echo "1. Configure SSL: docker compose -f docker-compose.production.yml run --rm certbot"
        echo "2. Execute migrações do banco (Supabase Dashboard)"
        echo "3. Teste a aplicação: https://alcahub.cloud"
        ;;

    2)
        echo -e "${GREEN}🔄 Atualizando aplicação...${NC}"

        # Pull do código
        echo -e "${BLUE}📥 Atualizando código...${NC}"
        git pull origin main || echo -e "${YELLOW}⚠️  Não foi possível fazer git pull${NC}"

        # Rebuild
        echo -e "${BLUE}🔨 Rebuilding...${NC}"
        docker compose -f docker-compose.production.yml build

        # Restart com recreate
        echo -e "${BLUE}🔄 Reiniciando serviços...${NC}"
        docker compose -f docker-compose.production.yml up -d --force-recreate

        # Ver logs
        echo -e "${BLUE}📋 Logs (Ctrl+C para sair):${NC}"
        docker compose -f docker-compose.production.yml logs -f --tail=50
        ;;

    3)
        echo -e "${GREEN}🔄 Reiniciando serviços...${NC}"
        docker compose -f docker-compose.production.yml restart

        echo -e "${BLUE}✅ Status:${NC}"
        docker compose -f docker-compose.production.yml ps
        ;;

    4)
        echo -e "${GREEN}📋 Logs (Ctrl+C para sair)${NC}"
        echo "Qual serviço?"
        echo "1) Todos"
        echo "2) Backend"
        echo "3) Frontend"
        echo "4) Nginx"
        read -p "Opção: " log_option

        case $log_option in
            1) docker compose -f docker-compose.production.yml logs -f ;;
            2) docker compose -f docker-compose.production.yml logs -f backend ;;
            3) docker compose -f docker-compose.production.yml logs -f frontend ;;
            4) docker compose -f docker-compose.production.yml logs -f nginx ;;
            *) echo "Opção inválida" ;;
        esac
        ;;

    5)
        echo -e "${GREEN}💾 Criando backup...${NC}"

        BACKUP_DIR="/var/backups/alca-financas"
        DATE=$(date +%Y%m%d_%H%M%S)

        mkdir -p $BACKUP_DIR

        # Backup de volumes
        echo -e "${BLUE}📦 Backup de volumes...${NC}"
        docker run --rm \
            -v alca-financas_backend-data:/data \
            -v $BACKUP_DIR:/backup \
            alpine tar czf /backup/backend-data-$DATE.tar.gz /data

        # Backup de configurações
        echo -e "${BLUE}📦 Backup de configurações...${NC}"
        tar czf $BACKUP_DIR/configs-$DATE.tar.gz \
            docker-compose.production.yml \
            .env \
            nginx/

        # Backup de imagens
        echo -e "${BLUE}📦 Backup de imagens Docker...${NC}"
        docker save alca-backend:latest | gzip > $BACKUP_DIR/backend-image-$DATE.tar.gz
        docker save alca-frontend:latest | gzip > $BACKUP_DIR/frontend-image-$DATE.tar.gz

        echo -e "${GREEN}✅ Backup concluído: $BACKUP_DIR${NC}"
        ls -lh $BACKUP_DIR/*$DATE*
        ;;

    6)
        echo -e "${GREEN}📊 Status dos containers:${NC}"
        echo ""
        docker compose -f docker-compose.production.yml ps
        echo ""
        echo -e "${BLUE}📊 Uso de recursos:${NC}"
        docker stats --no-stream
        ;;

    7)
        echo -e "${GREEN}👋 Saindo...${NC}"
        exit 0
        ;;

    *)
        echo -e "${RED}❌ Opção inválida${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Operação concluída!${NC}"
