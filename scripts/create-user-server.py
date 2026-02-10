#!/usr/bin/env python3
"""
DEPRECATED: Script para criar usuário no servidor de produção via SSH.

IMPORTANTE: Este script está DEPRECATED pois assume MongoDB no servidor remoto.
Para Supabase, use uma das alternativas abaixo.

ALTERNATIVAS RECOMENDADAS:

1. Via Supabase Dashboard (mais simples):
   - Acesse: https://app.supabase.com/project/_/auth/users
   - Clique em "Add user"
   - Preencha email e senha

2. Via SQL Editor do Supabase:
   - Use: scripts/sql-ensure-user-lezinrew.sql

3. Via Script Python Local (recomendado para automação):
   - Use: backend/scripts/set_user_password.py
   - Funciona local e remotamente se tiver acesso ao Supabase

4. Via API do Supabase (para integração):
   - Use Supabase Admin API
   - Requer SUPABASE_SERVICE_ROLE_KEY

Se você REALMENTE precisa criar usuários via SSH no servidor,
adapte este script para usar o backend/scripts/set_user_password.py
que já suporta Supabase.
"""

import sys

print("=" * 70)
print("⚠️  AVISO: Este script está DEPRECATED")
print("=" * 70)
print("")
print("Este script assumia MongoDB no servidor remoto.")
print("O projeto agora usa Supabase (PostgreSQL).")
print("")
print("📌 ALTERNATIVAS RECOMENDADAS:")
print("")
print("1️⃣  Via Supabase Dashboard (mais simples):")
print("   https://app.supabase.com/project/_/auth/users")
print("")
print("2️⃣  Via SQL Editor do Supabase:")
print("   Use: scripts/sql-ensure-user-lezinrew.sql")
print("")
print("3️⃣  Via Script Python (recomendado para automação):")
print("   cd backend")
print("   python scripts/set_user_password.py")
print("")
print("4️⃣  Via SSH no servidor + script Supabase:")
print("   ssh user@servidor")
print("   cd /var/www/alca-financas/backend")
print("   source venv/bin/activate")
print("   python scripts/set_user_password.py")
print("")
print("=" * 70)
print("")

sys.exit(1)
