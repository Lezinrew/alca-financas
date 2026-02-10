#!/usr/bin/env python3
"""
Script para instalar MongoDB localmente no servidor e configurar
"""

import subprocess
import sys
import time

# Configurações do servidor
SERVER_HOST = "alcahub.com.br"
SERVER_USER = "root"
SERVER_PASS = "4203434@Mudar"
PROJECT_DIR = "/var/www/alca-financas"
MONGO_DB = "alca_financas"

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

def main():
    print("🚀 Instalando MongoDB localmente no servidor...")
    print(f"Servidor: {SERVER_USER}@{SERVER_HOST}")
    
    # 1. Verificar se MongoDB já está instalado
    print_step("Verificando se MongoDB já está instalado...")
    stdout, stderr, code = execute_ssh("which mongod", check=False)
    if code == 0:
        print_warning("MongoDB já está instalado. Verificando status...")
        stdout, stderr, code = execute_ssh("systemctl is-active mongod", check=False)
        if stdout.strip() == "active":
            print_success("MongoDB já está rodando")
        else:
            print_step("Iniciando MongoDB...")
            execute_ssh("systemctl start mongod && systemctl enable mongod")
            print_success("MongoDB iniciado")
    else:
        # 2. Instalar MongoDB
        print_step("Instalando MongoDB...")
        
        # Detectar versão do Ubuntu/Debian
        stdout, _, _ = execute_ssh("lsb_release -rs", check=False)
        ubuntu_version = stdout.strip()
        
        if not ubuntu_version:
            # Tentar método alternativo
            stdout, _, _ = execute_ssh("cat /etc/os-release | grep VERSION_ID | cut -d '\"' -f 2", check=False)
            ubuntu_version = stdout.strip()
        
        print(f"Versão do sistema: {ubuntu_version}")
        
        # Instalar MongoDB usando método oficial
        print_step("Adicionando repositório MongoDB...")
        execute_ssh("""
            curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg && \
            echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        """)
        
        print_step("Atualizando pacotes e instalando MongoDB...")
        execute_ssh("""
            export DEBIAN_FRONTEND=noninteractive && \
            apt-get update -qq && \
            apt-get install -y -qq mongodb-org
        """)
        
        print_success("MongoDB instalado")
        
        # 3. Iniciar e habilitar MongoDB
        print_step("Iniciando MongoDB...")
        execute_ssh("systemctl start mongod && systemctl enable mongod")
        
        # Aguardar MongoDB iniciar
        print_step("Aguardando MongoDB iniciar...")
        time.sleep(5)
        
        # Verificar status
        stdout, stderr, code = execute_ssh("systemctl is-active mongod", check=False)
        if stdout.strip() == "active":
            print_success("MongoDB está rodando")
        else:
            print_error("MongoDB não iniciou corretamente")
            print_error("Verifique os logs: ssh root@alcahub.com.br 'journalctl -u mongod -n 50'")
            sys.exit(1)
    
    # 4. Criar banco de dados e usuário (opcional, mas recomendado)
    print_step("Configurando banco de dados...")
    
    # Verificar se o banco já existe
    stdout, stderr, code = execute_ssh(f"mongosh --quiet --eval 'db.getName()' {MONGO_DB}", check=False)
    
    # Criar banco de dados (MongoDB cria automaticamente ao usar)
    print_success(f"Banco de dados '{MONGO_DB}' será criado automaticamente na primeira conexão")
    
    # 5. Atualizar MONGO_URI no .env
    print_step("Atualizando MONGO_URI no arquivo .env...")
    
    mongo_uri = f"mongodb://localhost:27017/{MONGO_DB}"
    
    # Ler arquivo .env atual
    stdout, stderr, code = execute_ssh(f"cat {PROJECT_DIR}/backend/.env", check=False)
    if code != 0:
        print_error(f"Erro ao ler arquivo .env: {stderr}")
        sys.exit(1)
    
    env_content = stdout
    
    # Substituir MONGO_URI
    lines = env_content.split('\n')
    new_lines = []
    mongo_uri_found = False
    
    for line in lines:
        if line.startswith('MONGO_URI='):
            new_lines.append(f'MONGO_URI={mongo_uri}')
            mongo_uri_found = True
        else:
            new_lines.append(line)
    
    if not mongo_uri_found:
        # Adicionar se não existir
        new_lines.append(f'MONGO_URI={mongo_uri}')
    
    new_env_content = '\n'.join(new_lines)
    
    # Escrever novo arquivo .env
    env_escaped = new_env_content.replace('$', '\\$').replace('"', '\\"').replace('`', '\\`')
    execute_ssh(f'cat > {PROJECT_DIR}/backend/.env << "ENVEOF"\n{new_env_content}ENVEOF')
    
    print_success(f"MONGO_URI atualizado para: {mongo_uri}")
    
    # 6. Reiniciar serviço backend
    print_step("Reiniciando serviço backend...")
    execute_ssh("systemctl restart alca-financas")
    
    # Aguardar serviço iniciar
    print_step("Aguardando serviço backend iniciar...")
    time.sleep(5)
    
    # Verificar status
    stdout, stderr, code = execute_ssh("systemctl is-active alca-financas", check=False)
    if stdout.strip() == "active":
        print_success("Serviço backend está rodando")
        
        # Verificar se há erros recentes
        stdout, stderr, code = execute_ssh("journalctl -u alca-financas -n 10 --no-pager", check=False)
        if "error" in stdout.lower() or "exception" in stdout.lower():
            print_warning("Pode haver erros nos logs. Verifique:")
            print(f"   ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -n 50'")
        else:
            print_success("Backend conectado ao MongoDB com sucesso!")
    else:
        print_error("Serviço backend não iniciou corretamente")
        print_error("Verifique os logs:")
        print(f"   ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -n 50'")
        sys.exit(1)
    
    print("\n✅ MongoDB instalado e configurado com sucesso!")
    print(f"\n📊 Status:")
    stdout, _, _ = execute_ssh("systemctl is-active mongod", check=False)
    print(f"  MongoDB:  {stdout.strip()}")
    stdout, _, _ = execute_ssh("systemctl is-active alca-financas", check=False)
    print(f"  Backend:  {stdout.strip()}")
    
    print(f"\n📝 Informações:")
    print(f"  Connection String: {mongo_uri}")
    print(f"  Banco de dados: {MONGO_DB}")
    print(f"  Porta: 27017")
    
    print(f"\n🔍 Para verificar os logs:")
    print(f"   MongoDB:  ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u mongod -f'")
    print(f"   Backend:  ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -f'")
    print()

if __name__ == "__main__":
    main()

