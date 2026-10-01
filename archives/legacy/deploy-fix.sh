#!/bin/bash
# Script para fazer deploy do fix de transações

set -e

SERVER="alcaapp@76.13.239.220"
PROJECT_DIR="/home/alcaapp/alca-financas"

echo "🚀 Fazendo deploy do fix de transações..."

# 1. Fazer commit das mudanças
echo "📝 Commitando mudanças..."
git add backend/services/transaction_service.py
git commit -m "fix(transactions): remove non-existent columns account_tenant_id and category_tenant_id" || echo "Nada para commitar ou commit já feito"

# 2. Push para o repositório
echo "⬆️  Fazendo push..."
git push origin main

# 3. Conectar ao servidor e fazer pull + restart
echo "🔄 Atualizando servidor..."
ssh $SERVER << 'ENDSSH'
cd /home/alcaapp/alca-financas
echo "📥 Fazendo pull das atualizações..."
git pull origin main

echo "🔄 Reiniciando backend..."
sudo supervisorctl restart alca-backend

echo "✅ Deploy concluído!"
sudo supervisorctl status alca-backend
ENDSSH

echo ""
echo "✅ Deploy do fix concluído com sucesso!"
echo "🧪 Teste criando uma transação em: https://alcahub.cloud"
