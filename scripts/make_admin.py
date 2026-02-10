#!/usr/bin/env python3
"""
Script para tornar um usuário administrador.

Uso:
    python scripts/make_admin.py <email>

Exemplo:
    python scripts/make_admin.py lezinrew@gmail.com

Requer SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY configurados no .env
"""
import os
import sys
from dotenv import load_dotenv

# Carrega .env do backend e da raiz
load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

def make_admin(email):
    """Promove um usuário a administrador no Supabase."""

    # Tenta obter credenciais do Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = (
        os.getenv('SUPABASE_SERVICE_ROLE_KEY') or
        os.getenv('SUPABASE_KEY') or
        os.getenv('SUPABASE_LEGACY_JWT')
    )

    if not supabase_url or not supabase_key:
        print("❌ Erro: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY não configurados")
        print("")
        print("Configure no arquivo backend/.env ou .env:")
        print("  SUPABASE_URL=https://seu-projeto.supabase.co")
        print("  SUPABASE_SERVICE_ROLE_KEY=eyJ...")
        print("")
        print("Obtenha as credenciais em:")
        print("  https://app.supabase.com/project/_/settings/api")
        return False

    try:
        from supabase import create_client
    except ImportError:
        print("❌ Erro: Módulo 'supabase' não encontrado")
        print("")
        print("Instale com:")
        print("  pip install supabase")
        print("")
        return False

    print(f"📡 Conectando ao Supabase: {supabase_url}")

    try:
        client = create_client(supabase_url, supabase_key)

        # Busca usuário por email (case-insensitive)
        response = client.table('users').select('id, email, name, is_admin').ilike('email', email).execute()

        if not response.data or len(response.data) == 0:
            print(f"❌ Usuário não encontrado: {email}")
            return False

        user = response.data[0]

        if user.get('is_admin'):
            print(f"ℹ️  Usuário {email} já é administrador.")
            return True

        # Atualiza para admin
        update_response = client.table('users').update({'is_admin': True}).eq('id', user['id']).execute()

        if update_response.data:
            print(f"✅ Usuário {email} promovido a administrador com sucesso!")
            print(f"   Nome: {user.get('name', 'N/A')}")
            print(f"   ID: {user['id']}")
            return True
        else:
            print(f"❌ Falha ao atualizar usuário {email}")
            return False

    except Exception as e:
        print(f"❌ Erro ao conectar ao Supabase: {e}")
        print("")
        print("Verifique se:")
        print("  1. SUPABASE_URL está correto")
        print("  2. SUPABASE_SERVICE_ROLE_KEY é válido (deve começar com 'eyJ' ou 'sb_secret_')")
        print("  3. A tabela 'users' existe no banco")
        print("  4. Você tem permissões para atualizar a tabela")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/make_admin.py <email>")
        print("")
        print("Exemplo:")
        print("  python scripts/make_admin.py lezinrew@gmail.com")
        sys.exit(1)

    email = sys.argv[1]
    success = make_admin(email)
    sys.exit(0 if success else 1)
