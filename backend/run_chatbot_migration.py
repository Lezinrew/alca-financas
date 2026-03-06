#!/usr/bin/env python3
"""
Script para executar a migração do chatbot
Cria a tabela chatbot_conversations no Supabase
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
load_dotenv()

def run_migration():
    """Executa a migração para criar tabela de conversas"""

    # Configurar Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("❌ Erro: SUPABASE_URL e SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY devem estar configurados")
        sys.exit(1)

    print("📡 Conectando ao Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)

    # Ler arquivo de migração
    migration_file = Path(__file__).parent / 'migrations' / 'add_chatbot_conversations.sql'

    if not migration_file.exists():
        print(f"❌ Arquivo de migração não encontrado: {migration_file}")
        sys.exit(1)

    print(f"📄 Lendo migração: {migration_file}")
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("🚀 Executando migração...")

    try:
        # Executar SQL via RPC ou query
        # Nota: Supabase Python client não tem método direto para executar SQL raw
        # Você precisará executar isso via Dashboard do Supabase ou usando psycopg2

        print("\n" + "="*60)
        print("⚠️  ATENÇÃO: Execute esta migração manualmente no Supabase")
        print("="*60)
        print("\n1. Acesse: https://supabase.com/dashboard")
        print("2. Selecione seu projeto")
        print("3. Vá em 'SQL Editor'")
        print("4. Cole o SQL abaixo e execute:\n")
        print("-" * 60)
        print(sql)
        print("-" * 60)
        print("\nOu execute diretamente via psql:")
        print(f"psql {os.getenv('SUPABASE_DB_URL', 'postgresql://...')} < {migration_file}")
        print("\n✅ Após executar, o chatbot estará pronto para produção!")

    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
        sys.exit(1)


if __name__ == '__main__':
    run_migration()
