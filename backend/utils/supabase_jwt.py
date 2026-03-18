"""
Validação de JWT do Supabase Auth.

Suporta dois modos:
1) HS256 (simétrico) via env `SUPABASE_JWT_SECRET` (recomendado quando JWKS não expõe keys).
2) RS256/ES256 (assimétrico) via JWKS em `/auth/v1/.well-known/jwks.json`.

Este módulo é intencionalmente pequeno e sem dependências extras além de PyJWT + requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
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


def verify_supabase_jwt(token: str, config: Optional[SupabaseJwtConfig] = None) -> Dict[str, Any]:
    """
    Verifica e decodifica um JWT emitido pelo Supabase.
    Retorna o payload (claims) se válido, levanta Exception caso inválido.
    """
    config = config or SupabaseJwtConfig.from_env()

    # Modo HS256: valida localmente com secret.
    if config.jwt_secret:
        return jwt.decode(
            token,
            config.jwt_secret,
            algorithms=["HS256"],
            issuer=config.issuer,
            audience=config.audience,
            options={"verify_aud": bool(config.audience)},
        )

    # Modo JWKS (RS256/ES256): buscar chaves públicas.
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("JWT sem 'kid' e SUPABASE_JWT_SECRET não configurado.")

    jwks = _get_jwks(config.jwks_url)
    keys = jwks.get("keys") or []
    if not keys:
        raise RuntimeError(
            "JWKS do Supabase não expõe chaves públicas. "
            "Configure SUPABASE_JWT_SECRET no backend (modo HS256) ou habilite chaves assimétricas no Supabase."
        )

    jwk = next((k for k in keys if k.get("kid") == kid), None)
    if not jwk:
        raise jwt.InvalidTokenError("Chave pública (kid) não encontrada no JWKS.")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk) if jwk.get("kty") == "RSA" else jwt.algorithms.ECAlgorithm.from_jwk(jwk)
    alg = header.get("alg") or "RS256"

    return jwt.decode(
        token,
        public_key,
        algorithms=[alg],
        issuer=config.issuer,
        audience=config.audience,
        options={"verify_aud": bool(config.audience)},
    )

