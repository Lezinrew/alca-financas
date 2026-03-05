# Observabilidade e SRE no Alça Finanças

Guia do que está implementado e como evoluir para demonstrar habilidades **DevOps/SRE** (métricas, logs, alertas, dashboards).

---

## O que já existe

### 1. Health check
- **GET /api/health** – retorna `{ "status": "ok" }`. Uso: load balancer, K8s liveness.

### 2. Métricas Prometheus
- **GET /api/metrics** – endpoint para scrape do Prometheus (texto no formato Prometheus).
- Métricas expostas:
  - **http_requests_total** – contagem de requisições por `method`, `path`, `status`.
  - **http_request_duration_seconds** – histogram de latência por `method` e `path`.
  - **app_info** – gauge com label `env` (ambiente).
- Paths com IDs dinâmicos são normalizados (ex.: `/api/accounts/abc-123` → `/api/accounts/:id`) para evitar cardinalidade alta.

**Dependência:** `prometheus-client` no `requirements.txt`. Se não estiver instalado, o app sobe sem métricas.

---

## Como usar as métricas (Prometheus + Grafana)

1. **Prometheus** – configurar um job para fazer scrape do backend:
   ```yaml
   scrape_configs:
     - job_name: 'alca-backend'
       metrics_path: /api/metrics
       static_configs:
         - targets: ['api.alcahub.cloud']
       scheme: https
   ```

2. **Grafana** – criar dashboard com:
   - Taxa de requisições: `rate(http_requests_total[5m])`
   - Latência p95: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
   - Erros 5xx: `sum(rate(http_requests_total{status=~"5.."}[5m]))`

3. **Alertas (Prometheus/Alertmanager ou Grafana)** – exemplos:
   - Latência p95 > 2s
   - Taxa de 5xx > 0.01/s
   - `up == 0` para o job do backend

---

## Próximos passos para mostrar skill SRE

| Área | O que fazer | Como mostrar |
|------|-------------|--------------|
| **Logs** | Logs estruturados (JSON) com nível, request_id, user_id; enviar para Loki/CloudWatch/Datadog | “Logs centralizados e pesquisáveis por request_id” |
| **Tracing** | OpenTelemetry no backend (e opcional no front) com trace_id em logs e métricas | “Tracing distribuído para debugar latência entre serviços” |
| **Alerting** | Regras no Prometheus + Alertmanager (ou Grafana) e runbooks no repo | “Alertas com runbooks em docs/runbooks” |
| **Dashboards** | Dashboard Grafana versionado (JSON no repo) com SLOs (disponibilidade, latência) | “Dashboard de SRE versionado no repositório” |
| **SLOs/SLIs** | Definir SLIs (ex.: disponibilidade 99.9%, p99 < 1s) e painel de error budget | “SLOs definidos e error budget no dashboard” |
| **On-call / runbooks** | Doc de runbooks (ex.: “502 no login” → checar backend + CORS) e contato | “Runbooks para incidentes comuns” |

---

## Como falar disso em processos seletivos / portfolio

- **Currículo / LinkedIn:**  
  “Observabilidade: métricas Prometheus (latência, throughput, erros), health checks e preparação para dashboards Grafana e alertas.”

- **Entrevista:**  
  “No projeto X temos health check para o load balancer, endpoint de métricas Prometheus para taxa de requisições e latência por rota. Os paths são normalizados para não explodir cardinalidade. O próximo passo é Grafana + alertas e runbooks.”

- **Repo:**  
  Manter este doc (`docs/OBSERVABILIDADE-SRE.md`) e, quando fizer, um `docs/runbooks/` com passos para incidentes comuns (ex.: 502, CORS, lentidão).

---

## Segurança do endpoint de métricas

- **/api/metrics** hoje está aberto. Em produção, recomenda-se:
  - Restringir por IP (ex.: só IP do Prometheus/Grafana), ou
  - Usar autenticação (Bearer token / basic) e configurar o Prometheus com o token, ou
  - Expor métricas em outra porta (ex.: 9090) não exposta na internet e só acessível internamente.
