#!/usr/bin/env python3
"""
Script de diagnóstico para validação JWT do Supabase.
Uso: python3 backend/debug_jwt.py <access_token>
"""

import sys
import os
import jwt
import json

# Carregar env
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
SUPABASE_JWT_AUD = os.getenv("SUPABASE_JWT_AUD", "").strip() or None

def debug_token(token: str):
    print("="*80)
    print("JWT DIAGNÓSTICO - Alça Finanças")
    print("="*80)

    # 1. Decodificar sem verificação para ver os claims
    print("\n[1] Claims do token (SEM verificação):")
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        print(json.dumps(unverified, indent=2))

        token_iss = unverified.get("iss")
        token_aud = unverified.get("aud")
        token_sub = unverified.get("sub")

        print(f"\n  - Issuer (iss): {token_iss}")
        print(f"  - Audience (aud): {token_aud}")
        print(f"  - Subject (sub/user_id): {token_sub}")

    except Exception as e:
        print(f"ERRO ao decodificar: {e}")
        return

    # 2. Configuração do backend
    print("\n[2] Configuração do backend (.env):")
    print(f"  - SUPABASE_URL: {SUPABASE_URL}")
    print(f"  - SUPABASE_JWT_SECRET: {'*' * 20}...{SUPABASE_JWT_SECRET[-4:] if SUPABASE_JWT_SECRET else 'NÃO CONFIGURADO'}")
    print(f"  - SUPABASE_JWT_AUD: {SUPABASE_JWT_AUD or 'NÃO CONFIGURADO'}")

    expected_issuer = f"{SUPABASE_URL.rstrip('/')}/auth/v1"
    print(f"\n  - Issuer esperado pelo código: {expected_issuer}")

    # 3. Validações
    print("\n[3] Validações:")

    # Issuer match?
    if token_iss == expected_issuer:
        print(f"  ✅ Issuer MATCH: {token_iss}")
    else:
        print(f"  ❌ Issuer MISMATCH!")
        print(f"     Token tem: {token_iss}")
        print(f"     Backend espera: {expected_issuer}")

    # Audience match?
    if SUPABASE_JWT_AUD:
        if token_aud == SUPABASE_JWT_AUD:
            print(f"  ✅ Audience MATCH: {token_aud}")
        else:
            print(f"  ❌ Audience MISMATCH!")
            print(f"     Token tem: {token_aud}")
            print(f"     Backend espera: {SUPABASE_JWT_AUD}")
    else:
        if token_aud:
            print(f"  ⚠️  Token tem audience ({token_aud}), mas backend NÃO valida (SUPABASE_JWT_AUD não configurado)")
            print(f"     PROBLEMA: PyJWT pode falhar mesmo sem verify_aud se o claim existir!")
        else:
            print(f"  ✅ Audience não presente no token e não validado pelo backend")

    # 4. Tentar validar com secret
    if not SUPABASE_JWT_SECRET:
        print("\n[4] VALIDAÇÃO IGNORADA: SUPABASE_JWT_SECRET não configurado")
        return

    print("\n[4] Tentando validar com SUPABASE_JWT_SECRET:")

    # Teste 1: Com issuer strict
    print("\n  [4.1] Com issuer strict + verify_aud=False:")
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            issuer=expected_issuer,
            options={"verify_aud": False}
        )
        print(f"  ✅ SUCESSO! User ID: {payload.get('sub')}")
    except jwt.InvalidIssuerError as e:
        print(f"  ❌ FALHA (Issuer): {e}")
    except jwt.ExpiredSignatureError as e:
        print(f"  ❌ FALHA (Expirado): {e}")
    except Exception as e:
        print(f"  ❌ FALHA (Outro): {type(e).__name__}: {e}")

    # Teste 2: Sem validar issuer
    print("\n  [4.2] SEM validar issuer (verify_signature=True, verify_iss=False):")
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_iss": False, "verify_aud": False}
        )
        print(f"  ✅ SUCESSO! User ID: {payload.get('sub')}")
    except jwt.ExpiredSignatureError as e:
        print(f"  ❌ FALHA (Expirado): {e}")
    except Exception as e:
        print(f"  ❌ FALHA: {type(e).__name__}: {e}")

    # Teste 3: Com audience (se configurado)
    if SUPABASE_JWT_AUD:
        print(f"\n  [4.3] Com issuer + audience ({SUPABASE_JWT_AUD}):")
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                issuer=expected_issuer,
                audience=SUPABASE_JWT_AUD,
                options={"verify_aud": True}
            )
            print(f"  ✅ SUCESSO! User ID: {payload.get('sub')}")
        except jwt.InvalidAudienceError as e:
            print(f"  ❌ FALHA (Audience): {e}")
        except jwt.InvalidIssuerError as e:
            print(f"  ❌ FALHA (Issuer): {e}")
        except Exception as e:
            print(f"  ❌ FALHA: {type(e).__name__}: {e}")

    print("\n" + "="*80)
    print("DIAGNÓSTICO COMPLETO")
    print("="*80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 backend/debug_jwt.py <access_token>")
        print("\nPara obter um access_token:")
        print("1. Faça login no frontend")
        print("2. Abra DevTools → Application → Local Storage → sb-*-auth-token")
        print("3. Copie o valor de 'access_token'")
        sys.exit(1)

    token = sys.argv[1]
    debug_token(token)
