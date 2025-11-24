#!/usr/bin/expect -f

###############################################################################
# Deploy Remoto - Alça Finanças para Hostinger
# Script usando expect para autenticação SSH
###############################################################################

set timeout 300
set server_host "alcahub.com.br"
set server_user "root"
set server_pass "4203434@Mudar"
set project_dir "/var/www/alca-financas"
set domain "alcahub.com.br"

# Gerar SECRET_KEY
set secret_key [exec python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null]

puts "Iniciando deploy remoto do Alca Financas..."
puts "Servidor: ${server_user}@${server_host}"
puts ""

spawn ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${server_user}@${server_host}

expect {
    "password:" {
        send "${server_pass}\r"
    }
    "yes/no" {
        send "yes\r"
        expect "password:"
        send "${server_pass}\r"
    }
}

expect "# "

# Atualizar sistema e instalar dependencias
puts "Atualizando sistema e instalando dependencias..."
send "export DEBIAN_FRONTEND=noninteractive && apt-get update -qq && apt-get install -y -qq git curl wget build-essential python3 python3-pip python3-venv nginx certbot python3-certbot-nginx && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1 && apt-get install -y -qq nodejs\r"
expect "# "
puts "Dependencias instaladas"
puts ""

# Criar diretório do projeto
puts "Criando diretorio do projeto..."
send "mkdir -p ${project_dir} && chown -R ${server_user}:${server_user} ${project_dir}\r"
expect "# "
puts "Diretorio criado"
puts ""

# Clonar ou atualizar repositório
puts "Clonando/atualizando repositorio..."
send "cd ${project_dir} && if [ -d '.git' ]; then git pull origin main || git pull origin master; else git clone https://github.com/Lezinrew/alca-financas.git .; fi\r"
expect "# "
puts "Repositorio atualizado"
puts ""

# Configurar backend
puts "Configurando backend..."
send "cd ${project_dir}/backend && if [ ! -d 'venv' ]; then python3 -m venv venv; fi && source venv/bin/activate && pip install --upgrade pip --quiet && pip install -r requirements.txt --quiet && pip install gunicorn --quiet && deactivate\r"
expect "# "

# Criar arquivo .env do backend
puts "Criando arquivo .env do backend..."
send "cat > ${project_dir}/backend/.env << 'ENVEOF'\n# Ambiente\nFLASK_ENV=production\nNODE_ENV=production\n\n# MongoDB (ATUALIZE COM SUA CONNECTION STRING)\nMONGO_URI=mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas\nMONGO_DB=alca_financas\n\n# JWT\nSECRET_KEY=${secret_key}\nJWT_EXPIRES_HOURS=24\n\n# CORS\nCORS_ORIGINS=https://${domain},https://www.${domain},https://app.${domain}\n\n# OAuth (opcional)\nGOOGLE_CLIENT_ID=\nGOOGLE_CLIENT_SECRET=\nENVEOF\n\r"
expect "# "
puts "IMPORTANTE: Atualize o MONGO_URI no arquivo ${project_dir}/backend/.env"
puts ""

# Configurar frontend
puts "Configurando frontend..."
send "cd ${project_dir}/frontend && npm install --silent\r"
expect "# "

# Criar arquivo .env.production do frontend
puts "Criando arquivo .env.production do frontend..."
send "echo 'VITE_API_URL=https://api.${domain}' > ${project_dir}/frontend/.env.production\r"
expect "# "

# Build do frontend
puts "Buildando frontend..."
send "cd ${project_dir}/frontend && npm run build\r"
expect "# "
puts "Frontend buildado"
puts ""

# Configurar Nginx
puts "Configurando Nginx..."
send "cat > /etc/nginx/sites-available/alca-financas << 'NGINXEOF'\n# Redirecionar HTTP para HTTPS\nserver {\n    listen 80;\n    server_name ${domain} www.${domain};\n    return 301 https://\\\$server_name\\\$request_uri;\n}\n\n# Servidor HTTPS\nserver {\n    listen 443 ssl http2;\n    server_name ${domain} www.${domain};\n\n    # Certificados SSL (serão gerados pelo Certbot)\n    ssl_certificate /etc/letsencrypt/live/${domain}/fullchain.pem;\n    ssl_certificate_key /etc/letsencrypt/live/${domain}/privkey.pem;\n\n    # Configurações SSL\n    ssl_protocols TLSv1.2 TLSv1.3;\n    ssl_ciphers HIGH:!aNULL:!MD5;\n    ssl_prefer_server_ciphers on;\n\n    # Frontend (React SPA)\n    location / {\n        root ${project_dir}/frontend/dist;\n        try_files \\\$uri \\\$uri/ /index.html;\n        index index.html;\n        \n        # Cache para assets estáticos\n        location ~* \\\\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {\n            expires 1y;\n            add_header Cache-Control \"public, immutable\";\n        }\n    }\n\n    # API Backend\n    location /api {\n        proxy_pass http://127.0.0.1:8001;\n        proxy_http_version 1.1;\n        proxy_set_header Upgrade \\\$http_upgrade;\n        proxy_set_header Connection 'upgrade';\n        proxy_set_header Host \\\$host;\n        proxy_set_header X-Real-IP \\\$remote_addr;\n        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto \\\$scheme;\n        proxy_cache_bypass \\\$http_upgrade;\n        \n        # Timeouts\n        proxy_connect_timeout 60s;\n        proxy_send_timeout 60s;\n        proxy_read_timeout 60s;\n    }\n\n    # Logs\n    access_log /var/log/nginx/alca-financas-access.log;\n    error_log /var/log/nginx/alca-financas-error.log;\n}\nNGINXEOF\n\r"
expect "# "

# Ativar site
send "ln -sf /etc/nginx/sites-available/alca-financas /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default && nginx -t\r"
expect "# "
puts "Nginx configurado"
puts ""

# Configurar Gunicorn
puts "Configurando Gunicorn..."
send "cat > ${project_dir}/backend/gunicorn_config.py << 'GUNICORNEOF'\nimport multiprocessing\n\nbind = \"127.0.0.1:8001\"\nworkers = multiprocessing.cpu_count() * 2 + 1\nworker_class = \"sync\"\ntimeout = 60\nkeepalive = 5\nmax_requests = 1000\nmax_requests_jitter = 50\npreload_app = True\naccesslog = \"/var/log/gunicorn/alca-financas-access.log\"\nerrorlog = \"/var/log/gunicorn/alca-financas-error.log\"\nloglevel = \"info\"\nGUNICORNEOF\n\r"
expect "# "

# Criar diretório de logs
send "mkdir -p /var/log/gunicorn && chown -R ${server_user}:${server_user} /var/log/gunicorn\r"
expect "# "
puts "Gunicorn configurado"
puts ""

# Configurar Systemd Service
puts "Configurando servico systemd..."
send "cat > /etc/systemd/system/alca-financas.service << 'SERVICEEOF'\n[Unit]\nDescription=Alca Financas Backend API\nAfter=network.target\n\n[Service]\nUser=${server_user}\nGroup=${server_user}\nWorkingDirectory=${project_dir}/backend\nEnvironment=\"PATH=${project_dir}/backend/venv/bin\"\nExecStart=${project_dir}/backend/venv/bin/gunicorn -c gunicorn_config.py app:app\nRestart=always\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target\nSERVICEEOF\n\r"
expect "# "

send "systemctl daemon-reload && systemctl enable alca-financas && systemctl start alca-financas\r"
expect "# "
puts "Servico systemd configurado"
puts ""

# Configurar SSL (Let's Encrypt) - pular se falhar
puts "Configurando SSL com Let's Encrypt..."
puts "Isso pode pedir um email. Use um email valido para notificacoes."
send "certbot --nginx -d ${domain} -d www.${domain} --non-interactive --agree-tos --email admin@${domain} --redirect || echo 'Certbot pode precisar de configuração manual'\r"
expect "# "
puts "SSL configurado"
puts ""

# Reiniciar serviços
puts "Reiniciando servicos..."
send "systemctl restart alca-financas && systemctl reload nginx\r"
expect "# "
puts "Servicos reiniciados"
puts ""

# Status final
puts "Deploy concluido!"
puts ""
puts "Status dos servicos:"
send "echo '  Backend:  ' \\$(systemctl is-active alca-financas 2>/dev/null || echo 'não configurado') && echo '  Nginx:    ' \\$(systemctl is-active nginx 2>/dev/null || echo 'não configurado')\r"
expect "# "

puts ""
puts "Proximos passos:"
puts "  1. Atualize o MONGO_URI em ${project_dir}/backend/.env"
puts "  2. Reinicie o serviço: ssh ${server_user}@${server_host} 'systemctl restart alca-financas'"
puts "  3. Acesse: https://${domain}"
puts "  4. Verifique os logs: ssh ${server_user}@${server_host} 'journalctl -u alca-financas -f'"
puts ""

send "exit\r"
expect eof

