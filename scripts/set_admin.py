#!/usr/bin/env python3
"""
Script para promover um usuário a administrador
Uso: python3 scripts/set_admin.py [email]
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório backend ao path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

def set_admin(email: str):
    """Define um usuário como administrador"""
    try:
        # Carregar variáveis de ambiente
        from dotenv import load_dotenv
        env_path = backend_path / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✅ Arquivo .env carregado de {env_path}")
        else:
            print(f"⚠️  Arquivo .env não encontrado em {env_path}")

        # Inicializar banco de dados
        from database import init_db, get_db_type
        from repositories.user_repository_supabase import UserRepository

        print("🔌 Conectando ao banco de dados...")
        init_db()
        db_type = get_db_type()
        print(f"✅ Conectado ao {db_type}")

        # Buscar usuário
        user_repo = UserRepository()
        print(f"\n🔍 Buscando usuário: {email}")
        user = user_repo.find_by_email(email)

        if not user:
            print(f"❌ Usuário não encontrado: {email}")
            print("\n💡 Dica: Verifique se o email está correto e se o usuário existe no sistema")
            return False

        print(f"✅ Usuário encontrado: {user.get('name', 'Sem nome')}")
        print(f"   ID: {user.get('id', 'N/A')}")
        print(f"   Email: {user.get('email', 'N/A')}")
        print(f"   Admin atual: {user.get('is_admin', False)}")
        print(f"   Bloqueado: {user.get('is_blocked', False)}")

        # Verificar se já é admin
        if user.get('is_admin', False):
            print("\n✅ Usuário já é administrador!")
            return True

        # Atualizar para admin
        print(f"\n🔧 Promovendo {email} a administrador...")
        success = user_repo.update(user['id'], {'is_admin': True})

        if success:
            print("✅ Usuário promovido a administrador com sucesso!")
            print("\n📋 Próximos passos:")
            print("   1. Faça logout do sistema")
            print("   2. Faça login novamente")
            print("   3. O link 'Painel Admin' aparecerá no menu do seu perfil")
            print("   4. Ou acesse diretamente: https://alcahub.cloud/admin/dashboard")
            return True
        else:
            print("❌ Erro ao promover usuário a administrador")
            return False

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("🔐 SCRIPT DE PROMOÇÃO A ADMINISTRADOR")
    print("=" * 60)

    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = "lezinrew@gmail.com"  # Email padrão

    success = set_admin(email)

    print("\n" + "=" * 60)
    if success:
        print("✅ OPERAÇÃO CONCLUÍDA COM SUCESSO")
    else:
        print("❌ OPERAÇÃO FALHOU")
    print("=" * 60)

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
