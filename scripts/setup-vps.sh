#!/usr/bin/env bash
# Script de configuração inicial do VPS Hostinger
# Executa no VPS como root
# Uso: bash <(curl -s https://raw.githubusercontent.com/Lezinrew/alca-financas/main/scripts/setup-vps.sh)

set -e

echo "========================================="
echo "Setup Inicial - VPS Hostinger"
echo "alcahub.com.br"
echo "========================================="

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "Execute como root: sudo bash $0"
    exit 1
fi

echo "[1/8] Atualizando sistema..."
apt update && apt upgrade -y

echo "[2/8] Instalando dependências..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    supervisor \
    curl

echo "[3/8] Instalando Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

echo "[4/8] Criando usuário alcaapp..."
if ! id -u alcaapp > /dev/null 2>&1; then
    useradd -m -s /bin/bash alcaapp
    echo "Usuário alcaapp criado"
else
    echo "Usuário alcaapp já existe"
fi

echo "[5/8] Configurando SSH para alcaapp..."
mkdir -p /home/alcaapp/.ssh
chmod 700 /home/alcaapp/.ssh
cp /root/.ssh/authorized_keys /home/alcaapp/.ssh/ 2>/dev/null || true
chown -R alcaapp:alcaapp /home/alcaapp/.ssh

echo "[6/8] Clonando repositório..."
su - alcaapp << 'ENDSU'
if [ ! -d "alca-financas" ]; then
    git clone https://github.com/Lezinrew/alca-financas.git
    cd alca-financas/backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "Repositório clonado e dependências instaladas"
else
    echo "Repositório já existe"
fi
ENDSU

echo "[7/8] Criando diretórios..."
mkdir -p /var/www/alcahub.com.br
chown -R www-data:www-data /var/www/alcahub.com.br

echo "[8/8] Configurando Supervisor..."
cat > /etc/supervisor/conf.d/alca-backend.conf << 'EOF'
[program:alca-backend]
command=/home/alcaapp/alca-financas/backend/venv/bin/gunicorn app:app -c gunicorn.conf.py
directory=/home/alcaapp/alca-financas/backend
user=alcaapp
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/alca-backend.log
environment=PATH="/home/alcaapp/alca-financas/backend/venv/bin"
EOF

supervisorctl reread
supervisorctl update

echo "========================================="
echo "Setup Inicial Completo!"
echo "========================================="
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "1. Configurar backend .env:"
echo "   nano /home/alcaapp/alca-financas/backend/.env"
echo "   (Copie o conteúdo de VPS_BACKEND_ENV.txt)"
echo ""
echo "2. Iniciar backend:"
echo "   supervisorctl start alca-backend"
echo ""
echo "3. Configurar Nginx para API:"
echo "   nano /etc/nginx/sites-available/api.alcahub.com.br"
echo "   (Copie config do guia DEPLOY_VPS_HOSTINGER.md)"
echo ""
echo "4. Ativar site API:"
echo "   ln -s /etc/nginx/sites-available/api.alcahub.com.br /etc/nginx/sites-enabled/"
echo "   nginx -t && systemctl reload nginx"
echo ""
echo "5. Configurar Nginx para Frontend:"
echo "   nano /etc/nginx/sites-available/alcahub.com.br"
echo "   (Copie config do guia DEPLOY_VPS_HOSTINGER.md)"
echo ""
echo "6. Ativar site Frontend:"
echo "   ln -s /etc/nginx/sites-available/alcahub.com.br /etc/nginx/sites-enabled/"
echo "   nginx -t && systemctl reload nginx"
echo ""
echo "7. Configurar DNS (apontar para este servidor):"
echo "   A @ -> $(curl -s ifconfig.me)"
echo "   A www -> $(curl -s ifconfig.me)"
echo "   A api -> $(curl -s ifconfig.me)"
echo ""
echo "8. Instalar SSL (após DNS propagar):"
echo "   certbot --nginx -d api.alcahub.com.br"
echo "   certbot --nginx -d alcahub.com.br -d www.alcahub.com.br"
echo ""
echo "========================================="
