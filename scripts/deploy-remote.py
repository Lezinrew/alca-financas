#!/usr/bin/env python3
"""
Deploy Remoto - Alça Finanças para Hostinger
Script Python para fazer deploy completo via SSH
"""

import subprocess
import secrets
import sys
import time

# Configurações do servidor
SERVER_HOST = "alcahub.com.br"
SERVER_USER = "root"
SERVER_PASS = "4203434@Mudar"
PROJECT_DIR = "/var/www/alca-financas"
DOMAIN = "alcahub.com.br"

# Gerar SECRET_KEY
SECRET_KEY = secrets.token_urlsafe(32)

def print_step(message):
    print(f"\n🔵 {message}")

def print_success(message):
    print(f"✅ {message}")

def print_warning(message):
    print(f"⚠️  {message}")

def print_error(message):
    print(f"❌ {message}")

def execute_ssh(command, check=True):
    """Executa comando remoto via SSH usando sshpass"""
    cmd = [
        "sshpass", "-p", SERVER_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{SERVER_USER}@{SERVER_HOST}",
        command
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        if check:
            print_error(f"Erro ao executar comando: {command}")
            print_error(f"Erro: {e.stderr}")
            sys.exit(1)
        return e.stdout, e.stderr, e.returncode
    except FileNotFoundError:
        print_error("sshpass não encontrado. Instale com: brew install hudochenkov/sshpass/sshpass")
        sys.exit(1)

def main():
    print("🚀 Iniciando deploy remoto do Alça Finanças...")
    print(f"Servidor: {SERVER_USER}@{SERVER_HOST}")
    
    # Testar conexão
    print_step("Testando conexão com o servidor...")
    stdout, stderr, code = execute_ssh("echo 'Conexão OK'", check=False)
    if code != 0:
        print_error("Não foi possível conectar ao servidor")
        print_error(f"Erro: {stderr}")
        sys.exit(1)
    print_success("Conectado ao servidor")
    
    # 1. Atualizar sistema e instalar dependências
    print_step("Atualizando sistema e instalando dependências...")
    execute_ssh("""
        export DEBIAN_FRONTEND=noninteractive && \
        apt-get update -qq && \
        apt-get install -y -qq git curl wget build-essential python3 python3-pip python3-venv nginx certbot python3-certbot-nginx && \
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1 && \
        apt-get install -y -qq nodejs
    """)
    print_success("Dependências instaladas")
    
    # 2. Criar diretório do projeto
    print_step("Criando diretório do projeto...")
    execute_ssh(f"mkdir -p {PROJECT_DIR} && chown -R {SERVER_USER}:{SERVER_USER} {PROJECT_DIR}")
    print_success("Diretório criado")
    
    # 3. Clonar ou atualizar repositório
    print_step("Clonando/atualizando repositório...")
    execute_ssh(f"""
        cd {PROJECT_DIR} && \
        if [ -d '.git' ]; then \
            git pull origin main || git pull origin master; \
        else \
            git clone https://github.com/Lezinrew/alca-financas.git .; \
        fi
    """)
    print_success("Repositório atualizado")
    
    # 4. Configurar backend
    print_step("Configurando backend...")
    execute_ssh(f"""
        cd {PROJECT_DIR}/backend && \
        if [ ! -d 'venv' ]; then python3 -m venv venv; fi && \
        source venv/bin/activate && \
        pip install --upgrade pip --quiet && \
        pip install -r requirements.txt --quiet && \
        pip install gunicorn --quiet && \
        deactivate
    """)
    
    # Criar arquivo .env do backend
    print_step("Criando arquivo .env do backend...")
    env_content = f"""# Ambiente
FLASK_ENV=production
NODE_ENV=production

# MongoDB (ATUALIZE COM SUA CONNECTION STRING)
MONGO_URI=mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas
MONGO_DB=alca_financas

# JWT
SECRET_KEY={SECRET_KEY}
JWT_EXPIRES_HOURS=24

# CORS
CORS_ORIGINS=https://{DOMAIN},https://www.{DOMAIN},https://app.{DOMAIN}

# OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
"""
    # Escapar o conteúdo para o comando SSH
    env_escaped = env_content.replace('$', '\\$').replace('"', '\\"').replace('`', '\\`')
    execute_ssh(f'cat > {PROJECT_DIR}/backend/.env << "ENVEOF"\n{env_content}ENVEOF')
    print_warning(f"IMPORTANTE: Atualize o MONGO_URI no arquivo {PROJECT_DIR}/backend/.env")
    
    # 5. Configurar frontend
    print_step("Configurando frontend...")
    execute_ssh(f"cd {PROJECT_DIR}/frontend && npm install --silent")
    
    # Criar arquivo .env.production do frontend
    print_step("Criando arquivo .env.production do frontend...")
    execute_ssh(f'echo "VITE_API_URL=https://api.{DOMAIN}" > {PROJECT_DIR}/frontend/.env.production')
    
    # Build do frontend
    print_step("Buildando frontend...")
    execute_ssh(f"cd {PROJECT_DIR}/frontend && npm run build")
    print_success("Frontend buildado")
    
    # 6. Configurar Nginx (primeiro sem SSL)
    print_step("Configurando Nginx (HTTP inicial)...")
    nginx_config_http = f"""# Servidor HTTP inicial (antes do SSL)
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};

    # Frontend (React SPA)
    location / {{
        root {PROJECT_DIR}/frontend/dist;
        try_files $uri $uri/ /index.html;
        index index.html;
        
        # Cache para assets estáticos
        location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {{
            expires 1y;
            add_header Cache-Control "public, immutable";
        }}
    }}

    # API Backend
    location /api {{
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}

    # Logs
    access_log /var/log/nginx/alca-financas-access.log;
    error_log /var/log/nginx/alca-financas-error.log;
}}
"""
    execute_ssh(f'cat > /etc/nginx/sites-available/alca-financas << "NGINXEOF"\n{nginx_config_http}NGINXEOF')
    
    # Ativar site
    execute_ssh("ln -sf /etc/nginx/sites-available/alca-financas /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default && nginx -t && systemctl reload nginx")
    print_success("Nginx configurado (HTTP)")
    
    # 7. Configurar Gunicorn
    print_step("Configurando Gunicorn...")
    gunicorn_config = """import multiprocessing

bind = "127.0.0.1:8001"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/var/log/gunicorn/alca-financas-access.log"
errorlog = "/var/log/gunicorn/alca-financas-error.log"
loglevel = "info"
"""
    execute_ssh(f'cat > {PROJECT_DIR}/backend/gunicorn_config.py << "GUNICORNEOF"\n{gunicorn_config}GUNICORNEOF')
    
    # Criar diretório de logs
    execute_ssh(f"mkdir -p /var/log/gunicorn && chown -R {SERVER_USER}:{SERVER_USER} /var/log/gunicorn")
    print_success("Gunicorn configurado")
    
    # 8. Configurar Systemd Service
    print_step("Configurando serviço systemd...")
    service_config = f"""[Unit]
Description=Alca Financas Backend API
After=network.target

[Service]
User={SERVER_USER}
Group={SERVER_USER}
WorkingDirectory={PROJECT_DIR}/backend
Environment="PATH={PROJECT_DIR}/backend/venv/bin"
ExecStart={PROJECT_DIR}/backend/venv/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    execute_ssh(f'cat > /etc/systemd/system/alca-financas.service << "SERVICEEOF"\n{service_config}SERVICEEOF')
    execute_ssh("systemctl daemon-reload && systemctl enable alca-financas && systemctl start alca-financas")
    print_success("Serviço systemd configurado")
    
    # 9. Configurar SSL (Let's Encrypt) - tentar, mas não falhar se não funcionar
    print_step("Configurando SSL com Let's Encrypt...")
    print_warning("Isso pode pedir um email. Use um email válido para notificações.")
    stdout, stderr, code = execute_ssh(
        f"certbot --nginx -d {DOMAIN} -d www.{DOMAIN} --non-interactive --agree-tos --email admin@{DOMAIN} --redirect",
        check=False
    )
    if code == 0:
        print_success("SSL configurado automaticamente pelo Certbot")
    else:
        print_warning("Certbot pode precisar de configuração manual.")
        print_warning("Execute manualmente: certbot --nginx -d {DOMAIN} -d www.{DOMAIN}")
    
    # 10. Reiniciar serviços
    print_step("Reiniciando serviços...")
    execute_ssh("systemctl restart alca-financas && systemctl reload nginx")
    print_success("Serviços reiniciados")
    
    # 11. Status final
    print("\n✅ Deploy concluído!")
    print("\n📊 Status dos serviços:")
    stdout, _, _ = execute_ssh("systemctl is-active alca-financas 2>/dev/null || echo 'não configurado'", check=False)
    print(f"  Backend:  {stdout.strip()}")
    stdout, _, _ = execute_ssh("systemctl is-active nginx 2>/dev/null || echo 'não configurado'", check=False)
    print(f"  Nginx:    {stdout.strip()}")
    
    print("\n📝 Próximos passos:")
    print(f"  1. Atualize o MONGO_URI em {PROJECT_DIR}/backend/.env")
    print(f"  2. Reinicie o serviço: ssh {SERVER_USER}@{SERVER_HOST} 'systemctl restart alca-financas'")
    print(f"  3. Acesse: https://{DOMAIN}")
    print(f"  4. Verifique os logs: ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -f'")
    print()

if __name__ == "__main__":
    main()

