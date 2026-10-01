BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email citext NOT NULL UNIQUE,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    password_hash text NOT NULL,
    global_role text NOT NULL DEFAULT 'user'
        CHECK (global_role IN ('admin', 'user')),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled', 'pending_deletion')),
    settings jsonb NOT NULL DEFAULT '{"theme":"light","currency":"BRL","language":"pt-BR"}'::jsonb,
    email_verified_at timestamptz,
    password_changed_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    last_activity_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (deleted_at IS NULL OR status = 'pending_deletion')
);

CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    csrf_hash bytea NOT NULL CHECK (octet_length(csrf_hash) = 32),
    remember_me boolean NOT NULL DEFAULT false,
    user_agent text,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE INDEX auth_sessions_user_active_idx
    ON auth_sessions (user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE password_reset_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (used_at IS NULL OR used_at >= created_at)
);

CREATE INDEX password_reset_tokens_user_active_idx
    ON password_reset_tokens (user_id, expires_at)
    WHERE used_at IS NULL;

CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (length(trim(name)) > 0),
    slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz
);

CREATE TRIGGER tenants_set_updated_at
BEFORE UPDATE ON tenants
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE tenant_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role text NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE INDEX tenant_members_user_idx ON tenant_members (user_id, tenant_id);

CREATE TRIGGER tenant_members_set_updated_at
BEFORE UPDATE ON tenant_members
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    type text NOT NULL CHECK (length(trim(type)) > 0),
    institution text,
    color text,
    icon text,
    currency char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = upper(currency)),
    initial_balance numeric(19,2) NOT NULL DEFAULT 0,
    closing_day smallint CHECK (closing_day BETWEEN 1 AND 31),
    due_day smallint CHECK (due_day BETWEEN 1 AND 31),
    card_type text,
    parent_account_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz,
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, name),
    FOREIGN KEY (parent_account_id, tenant_id)
        REFERENCES accounts(id, tenant_id) ON DELETE RESTRICT,
    CHECK (parent_account_id IS NULL OR parent_account_id <> id),
    CHECK (
        (type = 'credit_card' AND closing_day IS NOT NULL AND due_day IS NOT NULL)
        OR type <> 'credit_card'
    )
);

CREATE INDEX accounts_tenant_active_idx
    ON accounts (tenant_id, name)
    WHERE archived_at IS NULL;

CREATE TRIGGER accounts_set_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    normalized_name text GENERATED ALWAYS AS (lower(trim(name))) STORED,
    type text NOT NULL CHECK (type IN ('income', 'expense', 'both')),
    color text,
    icon text,
    description text,
    essential boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz,
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, type, normalized_name)
);

CREATE INDEX categories_tenant_active_idx
    ON categories (tenant_id, type, normalized_name)
    WHERE archived_at IS NULL;

CREATE TRIGGER categories_set_updated_at
BEFORE UPDATE ON categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    account_id uuid,
    filename text NOT NULL CHECK (length(trim(filename)) > 0),
    file_format text NOT NULL CHECK (file_format IN ('ofx', 'csv')),
    total_parsed integer NOT NULL DEFAULT 0 CHECK (total_parsed >= 0),
    imported_count integer NOT NULL DEFAULT 0 CHECK (imported_count >= 0),
    ignored_count integer NOT NULL DEFAULT 0 CHECK (ignored_count >= 0),
    duplicate_count integer NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    unclassified_count integer NOT NULL DEFAULT 0 CHECK (unclassified_count >= 0),
    total_income numeric(19,2) NOT NULL DEFAULT 0 CHECK (total_income >= 0),
    total_expense numeric(19,2) NOT NULL DEFAULT 0 CHECK (total_expense >= 0),
    total_transfer numeric(19,2) NOT NULL DEFAULT 0 CHECK (total_transfer >= 0),
    ledger_balance numeric(19,2),
    status text NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'completed', 'failed', 'rolled_back')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    rolled_back_at timestamptz,
    UNIQUE (id, tenant_id),
    FOREIGN KEY (account_id, tenant_id)
        REFERENCES accounts(id, tenant_id) ON DELETE RESTRICT,
    CHECK ((status = 'rolled_back') = (rolled_back_at IS NOT NULL)),
    CHECK (completed_at IS NULL OR completed_at >= created_at)
);

CREATE INDEX import_batches_tenant_created_idx
    ON import_batches (tenant_id, created_at DESC);

CREATE TABLE transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    account_id uuid NOT NULL,
    destination_account_id uuid,
    category_id uuid,
    import_batch_id uuid,
    description text NOT NULL CHECK (length(trim(description)) > 0),
    amount numeric(19,2) NOT NULL CHECK (amount > 0),
    type text NOT NULL CHECK (type IN ('income', 'expense', 'transfer')),
    occurred_on date NOT NULL,
    status text NOT NULL DEFAULT 'paid'
        CHECK (status IN ('paid', 'pending', 'canceled')),
    responsible_person text,
    is_recurring boolean NOT NULL DEFAULT false,
    installment_current integer,
    installment_total integer,
    tags text[] NOT NULL DEFAULT '{}',
    notes text,
    entry_source text NOT NULL DEFAULT 'manual'
        CHECK (entry_source IN ('manual', 'csv', 'ofx')),
    fitid text,
    dedup_key text,
    source_file text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    canceled_at timestamptz,
    UNIQUE (id, tenant_id),
    FOREIGN KEY (account_id, tenant_id)
        REFERENCES accounts(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (destination_account_id, tenant_id)
        REFERENCES accounts(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (category_id, tenant_id)
        REFERENCES categories(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (import_batch_id, tenant_id)
        REFERENCES import_batches(id, tenant_id) ON DELETE RESTRICT,
    CHECK (
        (type = 'transfer' AND destination_account_id IS NOT NULL
            AND destination_account_id <> account_id AND category_id IS NULL)
        OR
        (type <> 'transfer' AND destination_account_id IS NULL AND category_id IS NOT NULL)
    ),
    CHECK (
        (installment_current IS NULL AND installment_total IS NULL)
        OR
        (installment_current BETWEEN 1 AND installment_total AND installment_total > 0)
    ),
    CHECK ((status = 'canceled') = (canceled_at IS NOT NULL))
);

CREATE INDEX transactions_tenant_date_idx
    ON transactions (tenant_id, occurred_on DESC, id);
CREATE INDEX transactions_tenant_account_date_idx
    ON transactions (tenant_id, account_id, occurred_on DESC);
CREATE INDEX transactions_tenant_category_date_idx
    ON transactions (tenant_id, category_id, occurred_on DESC)
    WHERE category_id IS NOT NULL;
CREATE UNIQUE INDEX transactions_ofx_fitid_unique
    ON transactions (tenant_id, account_id, fitid)
    WHERE entry_source = 'ofx' AND fitid IS NOT NULL;
CREATE UNIQUE INDEX transactions_dedup_key_unique
    ON transactions (tenant_id, account_id, dedup_key)
    WHERE dedup_key IS NOT NULL;

CREATE TRIGGER transactions_set_updated_at
BEFORE UPDATE ON transactions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE payables (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    category_id uuid,
    origin_transaction_id uuid,
    title text NOT NULL CHECK (length(trim(title)) > 0),
    description text,
    subcategory text,
    amount_expected numeric(19,2) NOT NULL CHECK (amount_expected > 0),
    currency char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = upper(currency)),
    due_date date,
    competency_month date NOT NULL
        CHECK (competency_month = date_trunc('month', competency_month)::date),
    is_recurring boolean NOT NULL DEFAULT false,
    recurrence_type text,
    installment_current integer,
    installment_total integer,
    responsible_person text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    canceled_at timestamptz,
    UNIQUE (id, tenant_id),
    FOREIGN KEY (category_id, tenant_id)
        REFERENCES categories(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (origin_transaction_id, tenant_id)
        REFERENCES transactions(id, tenant_id) ON DELETE RESTRICT,
    CHECK (
        (is_recurring AND recurrence_type IS NOT NULL)
        OR (NOT is_recurring AND recurrence_type IS NULL)
    ),
    CHECK (
        (installment_current IS NULL AND installment_total IS NULL)
        OR
        (installment_current BETWEEN 1 AND installment_total AND installment_total > 0)
    )
);

CREATE INDEX payables_tenant_competency_idx
    ON payables (tenant_id, competency_month, due_date);
CREATE INDEX payables_tenant_due_open_idx
    ON payables (tenant_id, due_date)
    WHERE canceled_at IS NULL;

CREATE TRIGGER payables_set_updated_at
BEFORE UPDATE ON payables
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE payable_payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    payable_id uuid NOT NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    transaction_id uuid,
    amount numeric(19,2) NOT NULL CHECK (amount > 0),
    paid_at timestamptz NOT NULL,
    payment_method text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reversed_at timestamptz,
    reversal_reason text,
    FOREIGN KEY (payable_id, tenant_id)
        REFERENCES payables(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (transaction_id, tenant_id)
        REFERENCES transactions(id, tenant_id) ON DELETE RESTRICT,
    CHECK (
        (reversed_at IS NULL AND reversal_reason IS NULL)
        OR
        (reversed_at IS NOT NULL AND length(trim(reversal_reason)) > 0)
    )
);

CREATE UNIQUE INDEX payable_payments_transaction_unique
    ON payable_payments (tenant_id, transaction_id)
    WHERE transaction_id IS NOT NULL AND reversed_at IS NULL;
CREATE INDEX payable_payments_payable_active_idx
    ON payable_payments (tenant_id, payable_id, paid_at)
    WHERE reversed_at IS NULL;

CREATE TABLE audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE RESTRICT,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    event_type text NOT NULL CHECK (length(trim(event_type)) > 0),
    entity_type text,
    entity_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_events_tenant_created_idx
    ON audit_events (tenant_id, created_at DESC);
CREATE INDEX audit_events_actor_created_idx
    ON audit_events (actor_user_id, created_at DESC);

COMMIT;
