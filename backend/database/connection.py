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


def _is_production_env() -> bool:
    """
    Detecta se backend está em ambiente de produção.

    Critérios (ordem de precedência):
    1. REQUIRE_SERVICE_ROLE_KEY=true (forma explícita, override)
    2. FLASK_ENV=production (padrão Flask)
    3. APP_ENV=production (alternativa genérica)

    Retorna True se qualquer critério for atendido.
    """
    # 1. Forma explícita (máxima prioridade)
    require_service_role = os.getenv('REQUIRE_SERVICE_ROLE_KEY', '').strip().lower()
    if require_service_role in ('true', '1', 'yes'):
        return True

    # 2. FLASK_ENV (padrão do projeto)
    flask_env = os.getenv('FLASK_ENV', '').strip().lower()
    if flask_env == 'production':
        return True

    # 3. APP_ENV (fallback genérico)
    app_env = os.getenv('APP_ENV', '').strip().lower()
    if app_env == 'production':
        return True

    return False


def _log_supabase_jwt_key_role(api_key: str, is_production: bool = False) -> None:
    """
    Valida role do JWT como camada adicional de segurança.

    IMPORTANTE: Esta é validação COMPLEMENTAR, não substitui
    a exigência de SUPABASE_SERVICE_ROLE_KEY em produção.

    Em produção: Se role != service_role → RuntimeError
    Em dev: Se role != service_role → WARNING
    """
    if not api_key.startswith("eyJ"):
        return  # Não é JWT (ex: sb_secret_*), skip

    payload = _jwt_payload_unverified(api_key)
    role = payload.get("role")

    env_label = "PRODUÇÃO" if is_production else "DEV"

    if role == "service_role":
        logger.info(f"✅ JWT role=service_role ({env_label})")
        return

    error_msg = (
        f"JWT com role={role!r}. Backend em produção deve usar "
        "SUPABASE_SERVICE_ROLE_KEY (role=service_role) para bypass de RLS; "
        "com anon/authenticated, erros 42501 em INSERT/UPDATE são comuns."
    )

    if is_production:
        logger.error(f"❌ {env_label}: {error_msg}")
        raise RuntimeError(
            f"AMBIENTE PRODUÇÃO: JWT com role={role!r} não é permitido.\n"
            "Configure SUPABASE_SERVICE_ROLE_KEY (role=service_role).\n"
            "Obtenha em: Project Settings > API > service_role key"
        )
    else:
        logger.warning(f"⚠️  {env_label}: {error_msg}")


def _resolve_supabase_key() -> str:
    """
    Resolve a chave Supabase seguindo prioridade:
    1. SUPABASE_SERVICE_ROLE_KEY (backend produção)
    2. SUPABASE_ANON_KEY (dev/frontend)
    3. Legacy keys (dev apenas)

    Em produção (detectado via _is_production_env()):
    - Exige SUPABASE_SERVICE_ROLE_KEY obrigatoriamente
    - Falha imediatamente se ausente (RuntimeError)
    """
    is_production = _is_production_env()

    # Padrão oficial (backend)
    service_role = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
    if service_role:
        env_label = "PRODUÇÃO" if is_production else "DEV"
        logger.info(f"✅ Usando SUPABASE_SERVICE_ROLE_KEY ({env_label})")
        return service_role

    # PRODUÇÃO: Falha imediatamente se SERVICE_ROLE_KEY ausente
    if is_production:
        logger.error("❌ PRODUÇÃO: SUPABASE_SERVICE_ROLE_KEY não configurada")
        raise RuntimeError(
            "❌ AMBIENTE PRODUÇÃO: SUPABASE_SERVICE_ROLE_KEY é OBRIGATÓRIO.\n"
            "\n"
            "Detecção de produção via:\n"
            "  - REQUIRE_SERVICE_ROLE_KEY=true (forma explícita), OU\n"
            "  - FLASK_ENV=production, OU\n"
            "  - APP_ENV=production\n"
            "\n"
            "Backend em produção não pode usar SUPABASE_ANON_KEY (limitações de RLS).\n"
            "Configure: SUPABASE_SERVICE_ROLE_KEY=<sua-chave-service-role>\n"
            "Obtenha em: Project Settings > API > service_role key\n"
            "⚠️  NUNCA exponha ao frontend!"
        )

    # DEV: Fallback para ANON_KEY
    anon_key = (os.getenv('SUPABASE_ANON_KEY') or '').strip()
    if anon_key:
        logger.warning(
            "⚠️  DEV: Usando SUPABASE_ANON_KEY. "
            "Para operações admin, configure SUPABASE_SERVICE_ROLE_KEY"
        )
        return anon_key

    # Legacy: compatibilidade retroativa (dev apenas)
    legacy_jwt = (os.getenv('SUPABASE_LEGACY_JWT') or '').strip()
    if legacy_jwt and legacy_jwt.startswith('eyJ'):
        logger.warning(
            "⚠️  DEV: SUPABASE_LEGACY_JWT está deprecated. Use SUPABASE_SERVICE_ROLE_KEY"
        )
        return legacy_jwt

    # Fallback final: SUPABASE_KEY (ambíguo, deprecated, dev apenas)
    supabase_key = (os.getenv('SUPABASE_KEY') or '').strip()
    if supabase_key:
        logger.warning(
            "⚠️  DEV: SUPABASE_KEY está deprecated. Use SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_ANON_KEY"
        )
        return supabase_key

    return ''


def init_db():
    """Inicializa conexão com o Supabase."""
    is_production = _is_production_env()
    supabase_url = (os.getenv('SUPABASE_URL') or '').strip()

    # _resolve_supabase_key() já lança RuntimeError se produção sem SERVICE_ROLE_KEY
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

    # Validação genérica (produção já validada em _resolve_supabase_key)
    if not supabase_key:
        raise RuntimeError(
            "Nenhuma chave Supabase configurada.\n"
            "Para backend: SUPABASE_SERVICE_ROLE_KEY\n"
            "Para dev/frontend: SUPABASE_ANON_KEY\n"
            "Obtenha em: Project Settings > API"
        )

    # Validar formato da chave
    if not (supabase_key.startswith('eyJ') or supabase_key.startswith('sb_secret_')):
        raise RuntimeError(
            f"Chave Supabase inválida.\n"
            f"Deve começar com 'eyJ' (JWT) ou 'sb_secret_' (nova API key).\n"
            f"Chave atual: {supabase_key[:10]}..."
        )

    env_label = "PRODUÇÃO" if is_production else "DEV"
    logger.info(f"📡 Inicializando Supabase ({env_label})...")
    _init_supabase(supabase_url, supabase_key, is_production=is_production)


def _init_supabase(url: str, key: str, is_production: bool = False):
    """Inicializa cliente Supabase."""
    global _supabase_client, _db_pool

    db_url = os.getenv('SUPABASE_DB_URL')  # Opcional: conexão direta PostgreSQL

    from supabase import create_client

    env_label = "PRODUÇÃO" if is_production else "DEV"

    # Nova API key format (sb_secret_*)
    if key.startswith('sb_secret_'):
        # supabase-py requer JWT, usar workaround
        _FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwIn0.x"
        try:
            _supabase_client = create_client(url, _FAKE_JWT)
            _supabase_client.supabase_key = key
            _supabase_client.options.headers.update(_supabase_client._get_auth_headers())
            _supabase_client._postgrest = None
            logger.info(f"✅ Cliente Supabase inicializado (sb_secret_, {env_label})")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Supabase: {e}")
            raise
    else:
        # JWT format: validar role como camada adicional
        try:
            _log_supabase_jwt_key_role(key, is_production=is_production)
            _supabase_client = create_client(url, key)
            logger.info(f"✅ Cliente Supabase inicializado (JWT, {env_label})")
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
