#!/bin/bash
# Comandos de deploy para alcahub.cloud
# Execute no servidor após fazer git pull

set -e

echo "🎨 Atualizando Frontend..."
cd /home/alcaapp/alca-financas/frontend

# Instalar dependências (se houver novas)
npm install --silent

# Build do frontend com a nova logo
npm run build

# Copiar build para o diretório servido pelo Traefik
echo "📦 Copiando build para /var/www/alcahub.cloud..."
sudo rm -rf /var/www/alcahub.cloud/*
sudo cp -r dist/* /var/www/alcahub.cloud/

# Ajustar permissões
sudo chown -R www-data:www-data /var/www/alcahub.cloud/

echo ""
echo "🔧 Atualizando Backend..."
cd /home/alcaapp/alca-financas/backend

# Ativar venv e atualizar dependências
source venv/bin/activate
pip install -r requirements.txt --quiet

# Verificar se o serviço está rodando
if systemctl list-units --type=service --all | grep -q alca-backend; then
    echo "🔄 Reiniciando serviço backend..."
    sudo systemctl restart alca-backend
elif supervisorctl status | grep -q alca-backend; then
    echo "🔄 Reiniciando backend via supervisor..."
    sudo supervisorctl restart alca-backend
else
    echo "⚠️ Serviço backend não encontrado. Pode estar rodando em modo manual."
fi

deactivate

echo ""
echo "✅ Deploy concluído!"
echo ""
echo "🔍 Verificando serviços..."
echo "Frontend: https://alcahub.cloud"
echo "Backend: https://api.alcahub.cloud/api/health"
