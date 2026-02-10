#!/bin/bash

# Script para limpar banco de dados MongoDB (local e servidor)
# Uso: ./scripts/clear-all-databases.sh [--local-only] [--server-only]

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configurações do servidor
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
MONGO_DB="alca_financas"

CLEAR_LOCAL=true
CLEAR_SERVER=true

# Parse argumentos
if [[ "$1" == "--local-only" ]]; then
    CLEAR_SERVER=false
elif [[ "$1" == "--server-only" ]]; then
    CLEAR_LOCAL=false
fi

echo -e "${YELLOW}🗑️  Limpeza de Banco de Dados - Alça Finanças${NC}"
echo ""

# Confirmação
read -p "⚠️  Tem certeza que deseja limpar TODOS os dados? (digite 'sim' para confirmar): " confirm

if [ "$confirm" != "sim" ]; then
    echo -e "${RED}❌ Operação cancelada${NC}"
    exit 0
fi

echo ""

# ============================================
# LIMPAR BANCO LOCAL
# ============================================
if [ "$CLEAR_LOCAL" = true ]; then
    echo -e "${GREEN}📦 Limpando banco de dados LOCAL...${NC}"
    
    # Verifica se MongoDB está rodando localmente
    if mongosh --eval "db.version()" > /dev/null 2>&1; then
        mongosh --quiet --eval "
        use ${MONGO_DB}
        
        print('📊 Status antes da limpeza (LOCAL):');
        db.getCollectionNames().forEach(function(col) {
            var count = db[col].countDocuments();
            print('  ' + col + ': ' + count + ' documentos');
        });
        
        print('');
        print('🗑️  Removendo dados...');
        
        db.getCollectionNames().forEach(function(col) {
            var result = db[col].deleteMany({});
            print('  ✓ ' + col + ': ' + result.deletedCount + ' documentos removidos');
        });
        
        print('');
        print('📊 Status após limpeza (LOCAL):');
        db.getCollectionNames().forEach(function(col) {
            var count = db[col].countDocuments();
            print('  ' + col + ': ' + count + ' documentos');
        });
        " 2>/dev/null || echo -e "${YELLOW}⚠️  MongoDB local não está rodando ou não acessível${NC}"
        
        echo -e "${GREEN}✅ Banco local limpo!${NC}"
    else
        echo -e "${YELLOW}⚠️  MongoDB local não está rodando${NC}"
    fi
    echo ""
fi

# ============================================
# LIMPAR BANCO NO SERVIDOR
# ============================================
if [ "$CLEAR_SERVER" = true ]; then
    echo -e "${GREEN}🌐 Limpando banco de dados no SERVIDOR...${NC}"
    
    # Verifica se sshpass está instalado
    if ! command -v sshpass &> /dev/null; then
        echo -e "${RED}❌ sshpass não encontrado. Instale com: brew install hudochenkov/sshpass/sshpass${NC}"
        echo -e "${YELLOW}   Ou limpe manualmente via SSH${NC}"
    else
        read -sp "Digite a senha do servidor: " SERVER_PASS
        echo ""
        
        sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
            "$SERVER_USER@$SERVER_HOST" bash <<EOF
            echo "📊 Status antes da limpeza (SERVIDOR):"
            mongosh --quiet --eval "
            use ${MONGO_DB}
            
            db.getCollectionNames().forEach(function(col) {
                var count = db[col].countDocuments();
                print('  ' + col + ': ' + count + ' documentos');
            });
            " 2>/dev/null || echo "  (sem dados ou MongoDB não acessível)"
            
            echo ""
            echo "🗑️  Removendo dados..."
            
            mongosh --quiet --eval "
            use ${MONGO_DB}
            
            db.getCollectionNames().forEach(function(col) {
                var result = db[col].deleteMany({});
                print('  ✓ ' + col + ': ' + result.deletedCount + ' documentos removidos');
            });
            " 2>/dev/null || echo "  Erro ao limpar"
            
            echo ""
            echo "📊 Status após limpeza (SERVIDOR):"
            mongosh --quiet --eval "
            use ${MONGO_DB}
            
            db.getCollectionNames().forEach(function(col) {
                var count = db[col].countDocuments();
                print('  ' + col + ': ' + count + ' documentos');
            });
            " 2>/dev/null || echo "  (sem dados)"
EOF
        
        echo -e "${GREEN}✅ Banco no servidor limpo!${NC}"
    fi
    echo ""
fi

echo -e "${GREEN}✅ Limpeza concluída!${NC}"
echo ""
echo -e "${YELLOW}💡 Próximos passos:${NC}"
echo "   1. Faça logout no frontend (se estiver logado)"
echo "   2. Limpe o localStorage do navegador (F12 > Application > Storage > Clear)"
echo "   3. Crie um novo usuário para começar do zero"
echo "   4. Teste o login com Google OAuth"
echo ""

