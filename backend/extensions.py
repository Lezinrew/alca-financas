from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _default_limits_exempt() -> bool:
    """CORS preflight não deve consumir quota (evita 429 em cascata no dev/HMR)."""
    try:
        return request.method == "OPTIONS"
    except RuntimeError:
        return False


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"],
    default_limits_exempt_when=_default_limits_exempt,
)
