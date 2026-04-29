#!/usr/bin/env python3
"""
Script para testar importação OFX e verificar categorias não duplicadas.
Uso: python3 scripts/test_ofx_import.py
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório backend ao path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

def test_ofx_import():
    """Testa importação OFX e verifica categorias"""
    try:
        # Carregar variáveis de ambiente
        from dotenv import load_dotenv
        root_env_path = backend_path.parent / ".env"
        if root_env_path.exists():
            load_dotenv(root_env_path)
            print(f"✅ Arquivo .env carregado de {root_env_path}")

        # Inicializar banco de dados
        from database import init_db, get_db_type
        from database.connection import get_supabase

        print("🔌 Conectando ao banco de dados...")
        init_db()
        db_type = get_db_type()
        print(f"✅ Conectado ao {db_type}")

        supabase = get_supabase()

        # Ler arquivo OFX de teste
        ofx_file = backend_path.parent / "test_nubank.ofx"
        if not ofx_file.exists():
            print(f"❌ Arquivo OFX não encontrado: {ofx_file}")
            return False

        print(f"\n📂 Lendo arquivo OFX: {ofx_file}")
        with open(ofx_file, 'rb') as f:
            ofx_content = f.read()

        # Parse OFX
        from services.import_service import parse_import_file
        print("📋 Processando arquivo OFX...")
        format_type, transactions = parse_import_file(ofx_file.name, ofx_content)

        print(f"✅ Arquivo processado:")
        print(f"   Formato: {format_type}")
        print(f"   Transações encontradas: {len(transactions)}")

        # Mostrar transações
        print("\n📊 Transações:")
        for i, tx in enumerate(transactions, 1):
            print(f"   {i}. {tx.get('date')} - {tx.get('description')} - R$ {tx.get('amount'):.2f} ({tx.get('type')})")

        # Extrair categorias únicas das transações
        categories_in_file = set()
        for tx in transactions:
            desc = tx.get('description', '')
            # Simular detecção de categoria baseada na descrição
            if 'Casa' in desc:
                categories_in_file.add('Casa')
            elif 'Pix Enviado' in desc:
                categories_in_file.add('Pix Enviado')
            elif 'Outros' in desc:
                categories_in_file.add('Outros')
            elif 'Salário' in desc:
                categories_in_file.add('Salário')

        print(f"\n🏷️  Categorias esperadas no arquivo: {sorted(categories_in_file)}")

        # Buscar categorias no banco antes da importação
        print("\n🔍 Verificando categorias existentes no banco...")
        response = supabase.table('categories').select('*').execute()

        if response.data:
            categories = response.data
            print(f"✅ Total de categorias no banco (antes): {len(categories)}")

            # Agrupar por nome normalizado
            from collections import defaultdict
            groups = defaultdict(list)

            for cat in categories:
                user_id = cat.get('user_id')
                tenant_id = cat.get('tenant_id')
                tenant_key = str(tenant_id) if tenant_id else '__legacy_null__'
                cat_type = cat.get('type')
                name = cat.get('name', '')
                norm_name = name.strip().lower()
                norm_name = ' '.join(norm_name.split())

                key = (user_id, tenant_key, cat_type, norm_name)
                groups[key].append(cat)

            duplicates = {k: v for k, v in groups.items() if len(v) > 1}

            if duplicates:
                print(f"\n⚠️  FALHA: Encontrados {len(duplicates)} grupos duplicados ANTES da importação:")
                for (user_id, tenant_id, cat_type, norm_name), cats in duplicates.items():
                    print(f"   - {norm_name} ({cat_type}): {len(cats)} duplicados")
                return False
            else:
                print("✅ Nenhuma duplicação encontrada antes da importação")

            # Listar categorias relevantes (Casa, Outros, Pix Enviado)
            relevant_cats = [c for c in categories if any(
                keyword.lower() in c.get('name', '').lower()
                for keyword in ['casa', 'outros', 'pix enviado', 'pix', 'salário']
            )]

            if relevant_cats:
                print(f"\n📋 Categorias relevantes existentes ({len(relevant_cats)}):")
                for cat in relevant_cats:
                    print(f"   - {cat.get('name')} ({cat.get('type')}) [tenant: {cat.get('tenant_id')}]")
            else:
                print("\n📋 Nenhuma categoria relevante existente")

        print("\n" + "="*80)
        print("✅ TESTE CONCLUÍDO COM SUCESSO")
        print("="*80)
        print("\n💡 Próximos passos:")
        print("   1. Importar este arquivo OFX manualmente via interface web")
        print("   2. Verificar se categorias Casa, Outros e Pix Enviado não aparecem duplicadas")
        print("   3. Conferir dropdown de categorias na tela de transações")
        print(f"   4. Arquivo para upload: {ofx_file}")

        return True

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("=" * 80)
    print("🧪 TESTE DE IMPORTAÇÃO OFX NUBANK")
    print("=" * 80)

    success = test_ofx_import()

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
