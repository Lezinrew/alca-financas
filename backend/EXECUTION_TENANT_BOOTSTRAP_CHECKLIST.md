# Checklist operacional: incidente tenant/bootstrap

## 1) Sinais rápidos de saúde

- `POST /api/auth/bootstrap` retorna `200` com `tenant_id` preenchido.
- `GET /api/auth/me` retorna `200`.
- `GET /api/accounts` (com mesmo token) retorna `200`.
- Logs não mostram `tenant_bootstrap_failed` nem `tenant_required` para o usuário validado.

## 2) Diagnóstico rápido (copiar e executar)

### API

```bash
curl -sS -X POST "$API_URL/api/auth/bootstrap" -H "Authorization: Bearer $TOKEN"
curl -sS "$API_URL/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -sS "$API_URL/api/accounts" -H "Authorization: Bearer $TOKEN"
```

### SQL (Supabase)

```sql
-- auth.users x public.users por email normalizado
select
  lower(trim(au.email)) as email_norm,
  au.id as auth_user_id,
  pu.id as public_user_id
from auth.users au
left join public.users pu
  on lower(trim(pu.email)) = lower(trim(au.email))
where lower(trim(au.email)) = lower(trim(:email));

-- memberships do auth user
select tm.tenant_id, tm.role
from public.tenant_members tm
where tm.user_id = :auth_user_id;
```

## 3) Critério objetivo: saudável vs quebrado

- **Saudável**
  - existe `public.users.id = auth.users.id` para o email;
  - `tenant_members` tem ao menos 1 linha para esse `user_id`;
  - bootstrap e endpoints protegidos respondem `200`.

- **Quebrado**
  - `POST /api/auth/bootstrap` retorna `503 tenant_bootstrap_failed`;
  - endpoints protegidos retornam `403 tenant_required` após bootstrap;
  - conflito residual: email aponta para `public.users.id` diferente do `auth.users.id`.

## 4) Primeira ação em caso quebrado

- Rodar as migrations de reconciliação/hardening já aprovadas.
- Executar `scripts/sql/verify_bootstrap_rls_and_data.sql`.
- Repetir smoke (`health -> bootstrap -> me -> accounts`) antes de encerrar incidente.
