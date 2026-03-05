"""
Métricas Prometheus para observabilidade (SRE/DevOps).

Expõe:
- http_requests_total: contagem de requisições por method, path, status
- http_request_duration_seconds: duração das requisições (histogram)
- app_info: versão/ambiente (gauge)

Uso: Prometheus scrape em GET /api/metrics (ou /metrics).
"""
import time
from flask import request, g

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Métricas (só criadas se prometheus_client instalado)
REQUEST_COUNT = None
REQUEST_LATENCY = None
APP_INFO = None

if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total de requisições HTTP",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "Duração das requisições em segundos",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
    APP_INFO = Gauge("app_info", "Informação da aplicação", ["env"])


def _path_label(path: str) -> str:
    """Normaliza path para label (evita cardinalidade explosiva)."""
    if not path:
        return "/"
    parts = path.strip("/").split("/")
    # Agrupa IDs dinâmicos: /api/accounts/abc123 -> /api/accounts/:id
    if len(parts) >= 4 and parts[-1]:
        last = parts[-1]
        if len(last) >= 8 and (last.replace("-", "").isalnum() or last.isdigit()):
            parts[-1] = ":id"
    return "/" + "/".join(parts) if parts else "/"


def init_metrics(app):
    """Registra hooks de request e rota /api/metrics na app Flask."""
    if not PROMETHEUS_AVAILABLE:
        return

    env = app.config.get("ENV", "production")

    @app.before_request
    def _before():
        g._request_start = time.perf_counter()

    @app.after_request
    def _after(response):
        if hasattr(g, "_request_start"):
            path = _path_label(request.path)
            duration = time.perf_counter() - g._request_start
            status = response.status_code
            REQUEST_COUNT.labels(method=request.method, path=path, status=status).inc()
            REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        return response

    APP_INFO.labels(env=env).set(1)

    @app.route("/api/metrics", methods=["GET"])
    def metrics():
        """Endpoint para scrape do Prometheus."""
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
