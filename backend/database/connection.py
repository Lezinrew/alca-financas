"""
Conexão com Banco de Dados (Supabase/PostgreSQL apenas)
"""
import base64
import json
import os
import logging
from typing import Optional, Any, Dict

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

logger = logging.getLogger(__name__)

_supabase_client: Optional[Any] = None
_db_pool: Optional[Any] = None


def _jwt_payload_unverified(token: str) -> Dict[str, Any]:
    """Decodifica payload de JWT (sem validar assinatura) para diagnóstico de role."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    body = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(body.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _log_supabase_jwt_key_role(api_key: str) -> None:
    """
    Avisa se a chave JWT não é service_role. PostgREST aplica RLS para anon/authenticated;
    inserts em tabelas protegidas falham com 42501 se policies não baterem com o contexto.
    """
    if not api_key.startswith("eyJ"):
        return
    payload = _jwt_payload_unverified(api_key)
    role = payload.get("role")
    if role == "service_role":
        return
    logger.warning(
        "Chave Supabase em formato JWT com role=%r. O backend em produção deve usar "
        "SUPABASE_SERVICE_ROLE_KEY (role service_role) para bypass de RLS no PostgREST; "
        "com anon/authenticated, erros 42501 em INSERT/UPDATE são comuns.",
        role,
    )


def _resolve_supabase_key() -> str:
    """
    Resolve a chave Supabase seguindo prioridade padrão:
    1. SUPABASE_SERVICE_ROLE_KEY (padrão oficial, backend apenas)
    2. SUPABASE_ANON_KEY (fallback dev, frontend safe)
    3. Legacy: SUPABASE_KEY, SUPABASE_LEGACY_JWT (compatibilidade)

    IMPORTANTE:
    - SUPABASE_SERVICE_ROLE_KEY: Backend apenas, bypassa RLS (admin)
    - SUPABASE_ANON_KEY: Seguro para frontend, respeita RLS
    """
    # Padrão oficial (backend)
    service_role = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
    if service_role:
        return service_role

    # Fallback para dev (anon key é segura mas limitada)
    anon_key = (os.getenv('SUPABASE_ANON_KEY') or '').strip()
    if anon_key:
        logger.warning(
            "⚠️  Usando SUPABASE_ANON_KEY. Para operações admin, use SUPABASE_SERVICE_ROLE_KEY"
        )
        return anon_key

    # Legacy: compatibilidade retroativa
    legacy_jwt = (os.getenv('SUPABASE_LEGACY_JWT') or '').strip()
    if legacy_jwt and legacy_jwt.startswith('eyJ'):
        logger.warning(
            "⚠️  SUPABASE_LEGACY_JWT está deprecated. Use SUPABASE_SERVICE_ROLE_KEY"
        )
        return legacy_jwt

    # Fallback final: SUPABASE_KEY (ambíguo, deprecated)
    supabase_key = (os.getenv('SUPABASE_KEY') or '').strip()
    if supabase_key:
        logger.warning(
            "⚠️  SUPABASE_KEY está deprecated. Use SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_ANON_KEY"
        )
        return supabase_key

    return ''


def init_db():
    """Inicializa conexão com o Supabase."""
    supabase_url = (os.getenv('SUPABASE_URL') or '').strip()
    supabase_key = _resolve_supabase_key()

    if not SUPABASE_AVAILABLE:
        raise RuntimeError(
            "Pacote 'supabase' não instalado. Execute: pip install supabase"
        )
    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL não configurado.\n"
            "Defina no .env: SUPABASE_URL=https://your-project.supabase.co\n"
            "Obtenha em: Project Settings > API no Supabase Dashboard"
        )
    if not supabase_key:
        raise RuntimeError(
            "Nenhuma chave Supabase configurada.\n"
            "Para backend: SUPABASE_SERVICE_ROLE_KEY (Project Settings > API > service_role key)\n"
            "Para dev/frontend: SUPABASE_ANON_KEY (Project Settings > API > anon key)\n"
            "NUNCA exponha service_role_key ao frontend!"
        )

    # Validar formato da chave
    if not (supabase_key.startswith('eyJ') or supabase_key.startswith('sb_secret_')):
        raise RuntimeError(
            f"Chave Supabase inválida.\n"
            f"Deve começar com 'eyJ' (JWT) ou 'sb_secret_' (nova API key).\n"
            f"Chave atual começa com: {supabase_key[:10]}...\n"
            f"Obtenha a chave correta em: Project Settings > API"
        )

    logger.info("📡 Inicializando Supabase...")
    _init_supabase(supabase_url, supabase_key)


def _init_supabase(url: str, key: str):
    """Inicializa cliente Supabase."""
    global _supabase_client, _db_pool

    db_url = os.getenv('SUPABASE_DB_URL')  # Opcional: conexão direta PostgreSQL

    from supabase import create_client

    # Nova API key format (sb_secret_*)
    if key.startswith('sb_secret_'):
        # supabase-py requer JWT, usar workaround
        _FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwIn0.x"
        try:
            _supabase_client = create_client(url, _FAKE_JWT)
            _supabase_client.supabase_key = key
            _supabase_client.options.headers.update(_supabase_client._get_auth_headers())
            _supabase_client._postgrest = None
            logger.info("✅ Cliente Supabase inicializado (sb_secret_ key)")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Supabase: {e}")
            raise
    else:
        # JWT format (eyJ*): formato nativo
        try:
            _log_supabase_jwt_key_role(key)
            _supabase_client = create_client(url, key)
            logger.info("✅ Cliente Supabase inicializado com sucesso (JWT key)")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Supabase: {e}")
            raise

    # Pool PostgreSQL direto (opcional, para queries SQL raw)
    if db_url:
        try:
            from psycopg2 import pool
            from psycopg2.extras import RealDictCursor
            _db_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=db_url,
                cursor_factory=RealDictCursor
            )
            logger.info("✅ Pool de conexões PostgreSQL inicializado (opcional)")
        except Exception as e:
            logger.warning(f"⚠️  Pool PostgreSQL não inicializado: {e}")


def get_db():
    """Retorna o cliente Supabase."""
    if _supabase_client is None:
        init_db()
    return _supabase_client


def get_db_type() -> str:
    """Retorna o tipo de banco em uso (sempre 'supabase')."""
    return "supabase"


def get_supabase() -> Any:
    """Alias para get_db(). Retorna o cliente Supabase."""
    return get_db()


def get_db_connection():
    """
    Retorna uma conexão do pool PostgreSQL direto (opcional).
    Requer SUPABASE_DB_URL configurado.
    """
    if _db_pool is None:
        init_db()
    if _db_pool is None:
        raise RuntimeError(
            "Pool PostgreSQL não configurado.\n"
            "Configure SUPABASE_DB_URL para conexão direta ao PostgreSQL.\n"
            "Obtenha em: Project Settings > Database > Connection string (psycopg2)"
        )
    return _db_pool.getconn()


def return_db_connection(conn):
    """Devolve uma conexão ao pool PostgreSQL."""
    if _db_pool:
        _db_pool.putconn(conn)


def close_db():
    """Fecha todas as conexões."""
    global _supabase_client, _db_pool
    if _db_pool:
        try:
            _db_pool.closeall()
        except Exception:
            pass
        _db_pool = None
    _supabase_client = None
