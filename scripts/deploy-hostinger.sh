#!/bin/bash

###############################################################################
# Deploy Script - Alça Finanças para Hostinger
# Script simplificado para deploy rápido no servidor
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
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
SERVICE_NAME="alca-financas"

echo -e "${BLUE}🚀 Iniciando deploy do Alça Finanças...${NC}"
echo ""

# Verificar se está no diretório correto
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Diretório do projeto não encontrado: ${PROJECT_DIR}${NC}"
    echo "Execute: sudo mkdir -p ${PROJECT_DIR} && sudo chown \$USER:\$USER ${PROJECT_DIR}"
    exit 1
fi

cd "$PROJECT_DIR"

# 1. Atualizar código
echo -e "${BLUE}📥 Atualizando código do repositório...${NC}"
if [ -d ".git" ]; then
    git pull origin main || git pull origin master
else
    echo -e "${YELLOW}⚠️  Diretório não é um repositório Git. Pulando atualização.${NC}"
fi
echo ""

# 2. Backend
echo -e "${BLUE}🔧 Configurando backend...${NC}"
cd "$BACKEND_DIR"

# Verificar se venv existe
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Ambiente virtual não encontrado. Criando...${NC}"
    python3 -m venv venv
fi

# Ativar venv e instalar dependências
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install gunicorn --quiet
deactivate

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado!${NC}"
    echo "Crie o arquivo .env com as configurações necessárias."
    echo "Veja o guia em docs/DEPLOY-HOSTINGER.md"
fi

cd "$PROJECT_DIR"
echo ""

# 3. Frontend
echo -e "${BLUE}🎨 Buildando frontend...${NC}"
cd "$FRONTEND_DIR"

# Verificar se node_modules existe
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  node_modules não encontrado. Instalando dependências...${NC}"
    npm install
else
    npm install --silent
fi

# Verificar se .env.production existe
if [ ! -f ".env.production" ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env.production não encontrado!${NC}"
    echo "Crie o arquivo .env.production com VITE_API_URL configurado."
fi

# Build
npm run build

cd "$PROJECT_DIR"
echo ""

# 4. Verificar serviços
echo -e "${BLUE}🔍 Verificando serviços...${NC}"

# Verificar se serviço systemd existe
if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
    echo -e "${GREEN}✓ Serviço ${SERVICE_NAME} encontrado${NC}"
    
    # Reiniciar serviço
    echo -e "${BLUE}🔄 Reiniciando serviço backend...${NC}"
    sudo systemctl restart "${SERVICE_NAME}"
    
    # Verificar status
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo -e "${GREEN}✓ Serviço ${SERVICE_NAME} está rodando${NC}"
    else
        echo -e "${RED}❌ Serviço ${SERVICE_NAME} falhou ao iniciar${NC}"
        echo "Execute: sudo systemctl status ${SERVICE_NAME}"
    fi
else
    echo -e "${YELLOW}⚠️  Serviço ${SERVICE_NAME} não encontrado${NC}"
    echo "Configure o serviço systemd seguindo o guia em docs/DEPLOY-HOSTINGER.md"
fi

# Verificar Nginx
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx está rodando${NC}"
    echo -e "${BLUE}🔄 Recarregando Nginx...${NC}"
    sudo systemctl reload nginx
else
    echo -e "${YELLOW}⚠️  Nginx não está rodando${NC}"
    echo "Execute: sudo systemctl start nginx"
fi

echo ""

# 5. Resumo
echo -e "${GREEN}✅ Deploy concluído!${NC}"
echo ""
echo -e "${BLUE}📊 Status dos serviços:${NC}"
echo "  Backend:  $(sudo systemctl is-active ${SERVICE_NAME} 2>/dev/null || echo 'não configurado')"
echo "  Nginx:    $(sudo systemctl is-active nginx 2>/dev/null || echo 'não configurado')"
echo ""
echo -e "${BLUE}📝 Próximos passos:${NC}"
echo "  1. Verifique os logs: sudo journalctl -u ${SERVICE_NAME} -f"
echo "  2. Teste a aplicação no navegador"
echo "  3. Verifique os logs do Nginx se houver problemas"
echo ""

