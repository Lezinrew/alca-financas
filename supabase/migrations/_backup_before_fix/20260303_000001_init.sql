-- =============================================================================
-- Migration: 20260303_000001_init
-- Description: Base schema (tables, constraints, indexes only)
-- Dependencies: None
-- Author: Database Migration (cleaned from pg_dump)
-- =============================================================================
-- SCOPE: Tables, PRIMARY KEY, UNIQUE, CHECK constraints, Foreign Keys, Indexes
-- NOT IN SCOPE: Functions, Triggers, Policies (ver migrations posteriores)
-- =============================================================================

BEGIN;

-- Statement timeouts para operações DDL seguras
SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_min_messages = warning;

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- users: Usuários da aplicação (auth própria ou Supabase Auth)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    password bytea,
    settings jsonb DEFAULT '{"theme": "light", "currency": "BRL", "language": "pt"}'::jsonb,
    auth_providers jsonb DEFAULT '[]'::jsonb,
    is_admin boolean DEFAULT false,
    profile_picture text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- tenants: Organizações/workspaces (multi-tenant core)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tenants (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- tenant_members: Relação user ↔ tenant com role
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tenant_members (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT tenant_members_role_check CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text, 'viewer'::text])))
);

-- -----------------------------------------------------------------------------
-- categories: Categorias de transações (income/expense)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categories (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(20) NOT NULL,
    color character varying(7),
    icon character varying(50),
    description text,
    active boolean DEFAULT true,
    essential boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL,
    CONSTRAINT categories_type_check CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
);

-- -----------------------------------------------------------------------------
-- accounts: Contas bancárias, cartões, savings, etc
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.accounts (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(50) NOT NULL,
    color character varying(7),
    icon character varying(50),
    balance numeric(15,2) DEFAULT 0.00,
    currency character varying(3) DEFAULT 'BRL'::character varying,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    initial_balance numeric(15,2) DEFAULT 0.00,
    current_balance numeric(15,2) DEFAULT 0.00,
    institution character varying(255),
    is_active boolean DEFAULT true,
    closing_day integer,
    due_day integer,
    card_type character varying(50),
    account_id uuid,
    tenant_id uuid NOT NULL
);

-- -----------------------------------------------------------------------------
-- transactions: Transações financeiras (core do sistema)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transactions (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    category_id uuid,
    account_id uuid,
    description character varying(500) NOT NULL,
    amount numeric(15,2) NOT NULL,
    type character varying(20) NOT NULL,
    date date NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    responsible_person character varying(255),
    is_recurring boolean DEFAULT false,
    installment_info jsonb,
    tags text[],
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tenant_id uuid NOT NULL,
    account_tenant_id uuid NOT NULL,
    category_tenant_id uuid NOT NULL,
    CONSTRAINT transactions_account_tenant_matches CHECK ((account_tenant_id = tenant_id)),
    CONSTRAINT transactions_category_tenant_matches CHECK ((category_tenant_id = tenant_id)),
    CONSTRAINT transactions_status_check CHECK (((status)::text = ANY ((ARRAY['paid'::character varying, 'pending'::character varying, 'overdue'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT transactions_type_check CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
);

-- -----------------------------------------------------------------------------
-- oauth_states: Cache temporário de estados OAuth (CSRF protection)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.oauth_states (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    state character varying(255) NOT NULL,
    provider character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone NOT NULL
);

-- =============================================================================
-- PRIMARY KEYS
-- =============================================================================

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.oauth_states
    ADD CONSTRAINT oauth_states_pkey PRIMARY KEY (id);

-- =============================================================================
-- UNIQUE CONSTRAINTS
-- =============================================================================

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_slug_key UNIQUE (slug);

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_tenant_user_unique UNIQUE (tenant_id, user_id);

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_id_tenant_unique UNIQUE (id, tenant_id);

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_id_tenant_unique UNIQUE (id, tenant_id);

ALTER TABLE ONLY public.oauth_states
    ADD CONSTRAINT oauth_states_state_key UNIQUE (state);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================

-- tenant_members → tenants (CASCADE: deletar tenant remove memberships)
ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

-- tenant_members → users (CASCADE: deletar user remove memberships)
ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- categories → users (CASCADE: deletar user remove suas categories)
ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- accounts → users (CASCADE: deletar user remove suas contas)
ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- accounts → accounts (self-reference para credit card → bank account)
ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_account_id_fkey
    FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE SET NULL;

-- transactions → users (CASCADE: deletar user remove transações)
ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- transactions → categories (SET NULL: deletar categoria não remove transação)
ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_fkey
    FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE SET NULL;

-- transactions → accounts (SET NULL: deletar account não remove transação)
ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_fkey
    FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE SET NULL;

-- transactions → categories (composite FK para tenant matching)
ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_tenant_fk
    FOREIGN KEY (category_id, category_tenant_id)
    REFERENCES public.categories(id, tenant_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT;

-- transactions → accounts (composite FK para tenant matching)
ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_tenant_fk
    FOREIGN KEY (account_id, account_tenant_id)
    REFERENCES public.accounts(id, tenant_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- users
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users USING btree (email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON public.users USING btree (created_at);

-- tenant_members
CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant_id ON public.tenant_members USING btree (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_members_user_id ON public.tenant_members USING btree (user_id);

-- categories
CREATE INDEX IF NOT EXISTS idx_categories_user_id ON public.categories USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_categories_type ON public.categories USING btree (type);
CREATE INDEX IF NOT EXISTS idx_categories_active ON public.categories USING btree (active);
CREATE INDEX IF NOT EXISTS idx_categories_tenant_user ON public.categories USING btree (tenant_id, user_id);

-- accounts
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON public.accounts USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_active ON public.accounts USING btree (active);
CREATE INDEX IF NOT EXISTS idx_accounts_tenant_user ON public.accounts USING btree (tenant_id, user_id);

-- transactions (muitos indexes para queries de dashboard/reports)
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON public.transactions USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_category_id ON public.transactions USING btree (category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON public.transactions USING btree (account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON public.transactions USING btree (date);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON public.transactions USING btree (type);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON public.transactions USING btree (status);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON public.transactions USING btree (user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_tenant_user_date ON public.transactions USING btree (tenant_id, user_id, date DESC);

-- oauth_states (cleanup periódico por expires_at)
CREATE INDEX IF NOT EXISTS idx_oauth_states_state ON public.oauth_states USING btree (state);
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON public.oauth_states USING btree (expires_at);

COMMIT;

-- =============================================================================
-- Migration complete: Base schema ready
-- Next: 20260303_000002_functions.sql
-- =============================================================================
