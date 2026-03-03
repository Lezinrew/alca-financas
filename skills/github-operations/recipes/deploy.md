## Recipe: deploy

**Goal:** Realizar deploy em produção usando scripts padronizados e CI/CD.

### Via CI (recomendado)

1. **Garanta que o PR foi mergeado em `main`.**
2. **Verifique que o workflow `CI/CD Pipeline - Supabase` passou.**
3. **Acione o workflow de deploy (manual ou automático):**
   - `Deploy to Production` em `.github/workflows/deploy-production.yml`.
   - Escolha o ambiente (por padrão: `production`).

O workflow irá:
- Construir imagem backend.
- Buildar frontend.
- Enviar artefatos ao servidor.
- Rodar smoke tests.

### Via scripts (fallback/controlado)

No servidor de produção (ou em ambiente equivalente):

```bash
cd /var/www/alcahub
./scripts/prod/deploy.sh
```

Esse script deve ser **idempotente**: re-aplicar a mesma versão não deve quebrar o ambiente.

### Observabilidade pós-deploy

- Verificar logs de backend.
- Verificar erros de frontend (Sentry/console).
- Rodar manualmente smoke checks principais (login, dashboard, transações).

