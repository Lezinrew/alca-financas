#!/usr/bin/env python3
"""
Script para inspecionar categorias duplicadas no banco de dados.
Uso: python3 scripts/inspect_categories.py
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório backend ao path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

def inspect_duplicates():
    """Verifica se existem categorias duplicadas"""
    try:
        # Carregar variáveis de ambiente
        from dotenv import load_dotenv

        # Tentar carregar .env da raiz primeiro, depois backend/
        root_env_path = backend_path.parent / ".env"
        backend_env_path = backend_path / ".env"

        if root_env_path.exists():
            load_dotenv(root_env_path)
            print(f"✅ Arquivo .env carregado de {root_env_path}")
        elif backend_env_path.exists():
            load_dotenv(backend_env_path)
            print(f"✅ Arquivo .env carregado de {backend_env_path}")
        else:
            print(f"⚠️  Arquivo .env não encontrado em {root_env_path} ou {backend_env_path}")

        # Inicializar banco de dados
        from database import init_db, get_db_type
        from database.connection import get_supabase

        print("🔌 Conectando ao banco de dados...")
        init_db()
        db_type = get_db_type()
        print(f"✅ Conectado ao {db_type}")

        supabase = get_supabase()

        # Buscar todas categorias e agrupar manualmente
        print("\n🔍 Buscando todas as categorias para análise...")

        # Para evitar problemas de RLS, vamos buscar via service role
        response = supabase.table('categories').select('*').execute()

        if response.data:
            categories = response.data
            print(f"✅ Total de categorias no banco: {len(categories)}")

            # Agrupar por user_id, tenant_id, type e nome normalizado
            from collections import defaultdict
            groups = defaultdict(list)

            for cat in categories:
                user_id = cat.get('user_id')
                tenant_id = cat.get('tenant_id')
                # Usar mesmo valor sentinela da constraint
                tenant_key = str(tenant_id) if tenant_id else '__legacy_null__'
                cat_type = cat.get('type')
                name = cat.get('name', '')
                # Normalizar nome exatamente como na constraint
                norm_name = name.strip().lower()
                norm_name = ' '.join(norm_name.split())  # Remove espaços extras

                key = (user_id, tenant_key, cat_type, norm_name)
                groups[key].append(cat)

            # Filtrar apenas grupos com duplicados
            duplicates = {k: v for k, v in groups.items() if len(v) > 1}

            if duplicates:
                print(f"\n⚠️  Encontrados {len(duplicates)} grupos de categorias duplicadas:")
                print("=" * 80)

                for (user_id, tenant_id, cat_type, norm_name), cats in duplicates.items():
                    print(f"\nUser ID: {user_id}")
                    print(f"Tenant ID: {tenant_id}")
                    print(f"Tipo: {cat_type}")
                    print(f"Nome normalizado: {norm_name}")
                    print(f"Quantidade: {len(cats)}")
                    print(f"IDs: {[c['id'] for c in cats]}")
                    print(f"Nomes originais: {[c['name'] for c in cats]}")
                    print(f"Created at: {[c.get('created_at', 'N/A') for c in cats]}")
                    print("-" * 80)

                return False
            else:
                print("\n✅ Nenhuma categoria duplicada encontrada!")
                print(f"   Total de categorias únicas: {len(groups)}")
                return True
        else:
            print("⚠️  Nenhuma categoria encontrada no banco")
            return True

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("=" * 80)
    print("🔍 INSPEÇÃO DE CATEGORIAS DUPLICADAS")
    print("=" * 80)

    success = inspect_duplicates()

    print("\n" + "=" * 80)
    if success:
        print("✅ NENHUMA DUPLICAÇÃO ENCONTRADA - BANCO ESTÁ CONSISTENTE")
    else:
        print("⚠️  DUPLICAÇÕES ENCONTRADAS - VERIFICAR RESULTADOS ACIMA")
    print("=" * 80)

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
