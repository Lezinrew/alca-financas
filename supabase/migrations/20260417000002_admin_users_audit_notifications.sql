-- =============================================================================
-- Admin: role/status, lifecycle timestamps, audit log, idempotent notifications
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- -----------------------------------------------------------------------------
-- public.users: papel e ciclo de vida
-- -----------------------------------------------------------------------------
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'user';

-- Idempotente: reexecução no SQL Editor ou retry após falha parcial
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE public.users
  ADD CONSTRAINT users_role_check
  CHECK (role = ANY (ARRAY['admin'::text, 'user'::text]))
  NOT VALID;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';

ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_status_check;
ALTER TABLE public.users
  ADD CONSTRAINT users_status_check
  CHECK (status = ANY (ARRAY['active'::text, 'inactive'::text, 'pending_deletion'::text, 'disabled'::text]))
  NOT VALID;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS last_activity_at timestamptz;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS inactive_warning_sent_at timestamptz;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS scheduled_deletion_at timestamptz;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Backfill role a partir de is_admin legado
UPDATE public.users
SET role = 'admin'
WHERE COALESCE(is_admin, false) = true
  AND role IS DISTINCT FROM 'admin';

-- Sincroniza is_admin com role (mantém compatibilidade com código legado)
UPDATE public.users
SET is_admin = (role = 'admin')
WHERE is_admin IS DISTINCT FROM (role = 'admin');

-- Promoção explícita do administrador principal
UPDATE public.users
SET role = 'admin',
    is_admin = true,
    status = CASE WHEN status = 'disabled' THEN 'active' ELSE status END,
    updated_at = now()
WHERE lower(trim(email)) = lower(trim('lezinrew@gmail.com'));

ALTER TABLE public.users VALIDATE CONSTRAINT users_role_check;
ALTER TABLE public.users VALIDATE CONSTRAINT users_status_check;

CREATE INDEX IF NOT EXISTS users_role_idx ON public.users (role);
CREATE INDEX IF NOT EXISTS users_status_idx ON public.users (status);
CREATE INDEX IF NOT EXISTS users_last_activity_at_idx ON public.users (last_activity_at);
CREATE INDEX IF NOT EXISTS users_last_login_at_idx ON public.users (last_login_at);

-- -----------------------------------------------------------------------------
-- Auditoria administrativa (fonte de verdade no Postgres)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_audit_logs (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    actor_user_id uuid,
    actor_email text,
    target_user_id uuid,
    action text NOT NULL,
    details_json jsonb DEFAULT '{}'::jsonb,
    ip_address text,
    user_agent text,
    created_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT admin_audit_logs_pkey PRIMARY KEY (id),
    CONSTRAINT admin_audit_logs_actor_fk FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT admin_audit_logs_target_fk FOREIGN KEY (target_user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS admin_audit_logs_created_at_idx ON public.admin_audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS admin_audit_logs_action_idx ON public.admin_audit_logs (action);

ALTER TABLE public.admin_audit_logs ENABLE ROW LEVEL SECURITY;

-- Sem policies para authenticated/anon: acesso apenas via service_role (backend).

-- -----------------------------------------------------------------------------
-- Idempotência de notificações administrativas (evita e-mail duplicado)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_notification_delivery (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    event_type text NOT NULL,
    subject_user_id uuid NOT NULL,
    payload_json jsonb DEFAULT '{}'::jsonb,
    email_sent boolean DEFAULT false NOT NULL,
    last_error text,
    created_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT admin_notification_delivery_pkey PRIMARY KEY (id),
    CONSTRAINT admin_notification_delivery_unique UNIQUE (event_type, subject_user_id),
    CONSTRAINT admin_notification_delivery_user_fk FOREIGN KEY (subject_user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS admin_notification_delivery_created_idx
  ON public.admin_notification_delivery (created_at DESC);

ALTER TABLE public.admin_notification_delivery ENABLE ROW LEVEL SECURITY;

COMMIT;
