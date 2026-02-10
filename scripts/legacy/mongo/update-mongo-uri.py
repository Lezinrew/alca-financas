#!/usr/bin/env python3
"""
Script para atualizar MONGO_URI no servidor
"""

import subprocess
import sys

# Configurações do servidor
SERVER_HOST = "alcahub.com.br"
SERVER_USER = "root"
SERVER_PASS = "4203434@Mudar"
PROJECT_DIR = "/var/www/alca-financas"

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
            print(f"❌ Erro ao executar comando: {command}")
            print(f"Erro: {e.stderr}")
            sys.exit(1)
        return e.stdout, e.stderr, e.returncode

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/update-mongo-uri.py <MONGO_URI>")
        print("\nExemplo:")
        print("  python3 scripts/update-mongo-uri.py 'mongodb+srv://user:pass@cluster.mongodb.net/alca_financas'")
        print("  python3 scripts/update-mongo-uri.py 'mongodb://localhost:27017/alca_financas'")
        sys.exit(1)
    
    mongo_uri = sys.argv[1]
    
    print(f"🔄 Atualizando MONGO_URI no servidor...")
    
    # Ler arquivo .env atual
    stdout, stderr, code = execute_ssh(f"cat {PROJECT_DIR}/backend/.env", check=False)
    if code != 0:
        print(f"❌ Erro ao ler arquivo .env: {stderr}")
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
    
    print("✅ MONGO_URI atualizado")
    
    # Reiniciar serviço
    print("🔄 Reiniciando serviço backend...")
    execute_ssh("systemctl restart alca-financas")
    
    # Verificar status
    print("⏳ Aguardando serviço iniciar...")
    import time
    time.sleep(3)
    
    stdout, stderr, code = execute_ssh("systemctl is-active alca-financas", check=False)
    if stdout.strip() == "active":
        print("✅ Serviço backend está rodando")
    else:
        print("⚠️  Serviço pode não estar rodando. Verifique os logs:")
        print(f"   ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -n 20'")
    
    print("\n📝 Para verificar os logs:")
    print(f"   ssh {SERVER_USER}@{SERVER_HOST} 'journalctl -u alca-financas -f'")

if __name__ == "__main__":
    main()

