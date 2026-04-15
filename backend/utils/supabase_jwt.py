"""
Validação de JWT do Supabase Auth.

O modo de validação segue o `alg` do header (não verificado), não a presença isolada de
`SUPABASE_JWT_SECRET`:
1) HS256 (simétrico) via env `SUPABASE_JWT_SECRET`.
2) RS256/ES256 (assimétrico) via JWKS em `/auth/v1/.well-known/jwks.json`.

Este módulo é intencionalmente pequeno e sem dependências extras além de PyJWT + requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
import os
import time
import jwt
import requests


@dataclass(frozen=True)
class SupabaseJwtConfig:
    supabase_url: str
    jwt_secret: Optional[str] = None
    audience: Optional[str] = None

    @property
    def issuer(self) -> str:
        # Supabase JWT `iss` normalmente é `${SUPABASE_URL}/auth/v1`
        return self.supabase_url.rstrip("/") + "/auth/v1"

    @property
    def jwks_url(self) -> str:
        return self.issuer + "/.well-known/jwks.json"

    @staticmethod
    def from_env() -> "SupabaseJwtConfig":
        supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
        if not supabase_url:
            raise RuntimeError("SUPABASE_URL não definido no backend.")
        jwt_secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip() or None
        # Compatibilidade: JWT_SECRET/CHATBOT_JWT_SECRET são legados e ignorados
        # para evitar drift entre serviços. A fonte única é SUPABASE_JWT_SECRET.
        audience = (os.getenv("SUPABASE_JWT_AUD") or "").strip() or None
        return SupabaseJwtConfig(supabase_url=supabase_url, jwt_secret=jwt_secret, audience=audience)


_jwks_cache: Dict[str, Any] = {"fetched_at": 0.0, "jwks": None}


def _get_jwks(jwks_url: str, ttl_seconds: int = 600) -> Dict[str, Any]:
    now = time.time()
    if _jwks_cache["jwks"] is not None and (now - float(_jwks_cache["fetched_at"])) < ttl_seconds:
        return _jwks_cache["jwks"]
    resp = requests.get(jwks_url, timeout=5)
    resp.raise_for_status()
    jwks = resp.json()
    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks


_DECODE_OPTIONS = {
    "verify_signature": True,
    "verify_exp": True,
    "verify_nbf": True,
    "verify_iat": True,
    "verify_aud": False,
    "verify_iss": False,
}


def _decode_via_jwks(token: str, config: SupabaseJwtConfig, header: Mapping[str, Any]) -> Dict[str, Any]:
    kid = header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("JWT assimétrico sem 'kid'; não é possível resolver chave via JWKS.")

    jwks = _get_jwks(config.jwks_url)
    keys = jwks.get("keys") or []
    if not keys:
        raise RuntimeError(
            "JWKS do Supabase não expõe chaves públicas. "
            "Para tokens HS256 defina SUPABASE_JWT_SECRET; para RS256/ES256 habilite chaves no Supabase."
        )

    jwk = next((k for k in keys if k.get("kid") == kid), None)
    if not jwk:
        raise jwt.InvalidTokenError("Chave pública (kid) não encontrada no JWKS.")

    kty = jwk.get("kty")
    if kty == "RSA":
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    elif kty == "EC":
        public_key = jwt.algorithms.ECAlgorithm.from_jwk(jwk)
    else:
        raise jwt.InvalidTokenError(f"JWKS com kty não suportado: {kty!r}")

    alg = (header.get("alg") or "RS256").strip()
    return jwt.decode(token, public_key, algorithms=[alg], options=_DECODE_OPTIONS)


def verify_supabase_jwt(token: str, config: Optional[SupabaseJwtConfig] = None) -> Dict[str, Any]:
    """
    Verifica e decodifica um JWT emitido pelo Supabase.
    Retorna o payload (claims) se válido, levanta Exception caso inválido.

    IMPORTANTE: Validação de issuer/audience removida - apenas assinatura é validada.
    Supabase pode emitir tokens com iss="supabase" (legacy) ou iss="${URL}/auth/v1" (v2+).
    A escolha HS256 (secret) vs JWKS segue o campo `alg` do header, não só a presença do secret.
    """
    config = config or SupabaseJwtConfig.from_env()

    header = jwt.get_unverified_header(token)
    alg = (header.get("alg") or "HS256").strip()

    if alg == "HS256":
        if not config.jwt_secret:
            raise RuntimeError(
                "JWT com algoritmo HS256 exige SUPABASE_JWT_SECRET no backend (mesmo projeto que SUPABASE_URL)."
            )
        return jwt.decode(
            token,
            config.jwt_secret,
            algorithms=["HS256"],
            options=_DECODE_OPTIONS,
        )

    return _decode_via_jwks(token, config, header)

