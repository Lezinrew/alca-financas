#!/usr/bin/env python3
"""
DEPRECATED: Este script foi substituído por backend/scripts/set_user_password.py
que suporta tanto MongoDB quanto Supabase.

Para redefinir a senha do usuário lezinrew@gmail.com:

    cd backend
    python scripts/set_user_password.py

Ou use o script SQL direto no Supabase SQL Editor:
    scripts/sql-set-password-lezinrew.sql
"""
import sys
import os

print("⚠️  AVISO: Este script está DEPRECATED")
print("")
print("📌 Use em vez disso:")
print("")
print("   Opção 1 (Python - funciona com MongoDB e Supabase):")
print("   $ cd backend && python scripts/set_user_password.py")
print("")
print("   Opção 2 (SQL direto - apenas Supabase):")
print("   Execute o arquivo: scripts/sql-set-password-lezinrew.sql")
print("   no SQL Editor do Supabase Dashboard")
print("")
print("💡 Ambos os métodos redefinem a senha para '1234mudar'")
print("")

sys.exit(1)
