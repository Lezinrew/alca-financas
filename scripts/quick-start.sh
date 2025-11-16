#!/bin/bash

###############################################################################
# Quick Start - Alça Finanças
# Script simplificado para desenvolvimento rápido (sem Docker obrigatório)
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}⚡ Quick Start - Alça Finanças${NC}\n"

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Criando .env...${NC}"
    cp .env.example .env
fi

# Create logs directory
mkdir -p logs

# Start MongoDB
echo -e "${BLUE}🗄️  MongoDB${NC}"
./scripts/start-mongodb.sh
echo ""

# Backend setup
echo -e "${BLUE}🔧 Backend${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

echo "📦 Instalando dependências..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt 2>&1 | grep -v "already satisfied" || true

echo "🚀 Iniciando Backend..."
python app.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
echo -e "${GREEN}✅ Backend rodando (PID: $BACKEND_PID)${NC}"

cd ..

# Frontend setup
echo -e "\n${BLUE}🎨 Frontend${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências..."
    npm install --silent
else
    echo "✅ Dependências já instaladas"
fi

echo "🚀 Iniciando Frontend..."
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
echo -e "${GREEN}✅ Frontend rodando (PID: $FRONTEND_PID)${NC}"

cd ..

# Wait for services
echo -e "\n⏳ Aguardando serviços iniciarem..."
sleep 3

# Health check
echo -e "\n${BLUE}🏥 Health Check${NC}"

# Detect backend port
BACKEND_PORT=5000
if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
    BACKEND_PORT=8001
fi

# Check backend
if curl -s http://localhost:${BACKEND_PORT}/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API: http://localhost:${BACKEND_PORT}${NC}"
else
    echo -e "${YELLOW}⚠️  Backend ainda iniciando...${NC}"
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend: http://localhost:3000${NC}"
elif curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend: http://localhost:5173${NC} (Vite default)"
else
    echo -e "${YELLOW}⚠️  Frontend ainda iniciando... (pode levar 10-20 segundos)${NC}"
fi

# Final info
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Alça Finanças está rodando!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "📍 ${BLUE}URLs:${NC}"
echo -e "   🌐 Frontend:  ${YELLOW}http://localhost:3000${NC} ou ${YELLOW}http://localhost:5173${NC}"
echo -e "   🔧 Backend:   ${YELLOW}http://localhost:${BACKEND_PORT}${NC}"
echo -e "   🗄️  MongoDB:   ${YELLOW}mongodb://localhost:27017${NC}"
echo ""
echo -e "📝 ${BLUE}Logs:${NC}"
echo -e "   Backend:  ${YELLOW}tail -f logs/backend.log${NC}"
echo -e "   Frontend: ${YELLOW}tail -f logs/frontend.log${NC}"
echo ""
echo -e "🛑 ${BLUE}Para parar:${NC}"
echo -e "   ${YELLOW}./scripts/stop-local.sh${NC}"
echo ""
