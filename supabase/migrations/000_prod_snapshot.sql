-- =============================================================================
-- 000_prod_snapshot.sql
-- Snapshot canônico do schema public do Supabase (Alça Finanças)
-- Objetivo: reproduzir o estado atual do banco (public) sem depender do SQL Editor
-- =============================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_min_messages = warning;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

--
-- PostgreSQL database dump
--


-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: current_app_user_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_app_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid;
$$;


--
-- Name: FUNCTION current_app_user_id(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.current_app_user_id() IS 'Retorna o user_id definido por set_config(app.current_user_id, ...) na sessão. Usado por RLS quando não se usa Supabase Auth.';


--
-- Name: current_tenant_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_tenant_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claim.tenant_id', true), '')::uuid,
    NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  );
$$;


--
-- Name: FUNCTION current_tenant_id(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.current_tenant_id() IS 'Returns the current tenant_id from JWT claim (request.jwt.claim.tenant_id) or app.current_tenant_id session variable.';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
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
    tenant_id uuid DEFAULT public.current_tenant_id() NOT NULL
);


--
-- Name: dev_seed_account(text, text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dev_seed_account(p_name text, p_type text, p_user_id uuid, p_tenant_id uuid) RETURNS public.accounts
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  v_row public.accounts;
begin
  insert into public.accounts (name, type, user_id, tenant_id)
  values (p_name, p_type, p_user_id, p_tenant_id)
  returning * into v_row;

  return v_row;
end;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
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
    tenant_id uuid DEFAULT public.current_tenant_id() NOT NULL,
    CONSTRAINT categories_type_check CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
);


--
-- Name: oauth_states; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oauth_states (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    state character varying(255) NOT NULL,
    provider character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: tenant_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_members (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT tenant_members_role_check CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text, 'viewer'::text])))
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
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
    tenant_id uuid DEFAULT public.current_tenant_id() NOT NULL,
    account_tenant_id uuid NOT NULL,
    category_tenant_id uuid NOT NULL,
    CONSTRAINT transactions_account_tenant_matches CHECK ((account_tenant_id = tenant_id)),
    CONSTRAINT transactions_category_tenant_matches CHECK ((category_tenant_id = tenant_id)),
    CONSTRAINT transactions_status_check CHECK (((status)::text = ANY ((ARRAY['paid'::character varying, 'pending'::character varying, 'overdue'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT transactions_type_check CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
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


--
-- Name: accounts accounts_id_tenant_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_id_tenant_unique UNIQUE (id, tenant_id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: categories categories_id_tenant_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_id_tenant_unique UNIQUE (id, tenant_id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: oauth_states oauth_states_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_states
    ADD CONSTRAINT oauth_states_pkey PRIMARY KEY (id);


--
-- Name: oauth_states oauth_states_state_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_states
    ADD CONSTRAINT oauth_states_state_key UNIQUE (state);


--
-- Name: tenant_members tenant_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_pkey PRIMARY KEY (id);


--
-- Name: tenant_members tenant_members_tenant_user_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_tenant_user_unique UNIQUE (tenant_id, user_id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_slug_key UNIQUE (slug);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_accounts_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounts_active ON public.accounts USING btree (active);


--
-- Name: idx_accounts_tenant_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounts_tenant_user ON public.accounts USING btree (tenant_id, user_id);


--
-- Name: idx_accounts_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounts_user_id ON public.accounts USING btree (user_id);


--
-- Name: idx_categories_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_active ON public.categories USING btree (active);


--
-- Name: idx_categories_tenant_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_tenant_user ON public.categories USING btree (tenant_id, user_id);


--
-- Name: idx_categories_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_type ON public.categories USING btree (type);


--
-- Name: idx_categories_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_user_id ON public.categories USING btree (user_id);


--
-- Name: idx_oauth_states_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_states_expires_at ON public.oauth_states USING btree (expires_at);


--
-- Name: idx_oauth_states_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oauth_states_state ON public.oauth_states USING btree (state);


--
-- Name: idx_tenant_members_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_members_tenant_id ON public.tenant_members USING btree (tenant_id);


--
-- Name: idx_tenant_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_members_user_id ON public.tenant_members USING btree (user_id);


--
-- Name: idx_transactions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_account_id ON public.transactions USING btree (account_id);


--
-- Name: idx_transactions_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_category_id ON public.transactions USING btree (category_id);


--
-- Name: idx_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_date ON public.transactions USING btree (date);


--
-- Name: idx_transactions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_status ON public.transactions USING btree (status);


--
-- Name: idx_transactions_tenant_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_tenant_user_date ON public.transactions USING btree (tenant_id, user_id, date DESC);


--
-- Name: idx_transactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_type ON public.transactions USING btree (type);


--
-- Name: idx_transactions_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_user_date ON public.transactions USING btree (user_id, date DESC);


--
-- Name: idx_transactions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_user_id ON public.transactions USING btree (user_id);


--
-- Name: idx_users_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_created_at ON public.users USING btree (created_at);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: accounts update_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: categories update_categories_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON public.categories FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: transactions update_transactions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: accounts accounts_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE SET NULL;


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: categories categories_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tenant_members tenant_members_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_members tenant_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_members
    ADD CONSTRAINT tenant_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE SET NULL;


--
-- Name: transactions transactions_account_id_tenant_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_tenant_fk FOREIGN KEY (account_id, account_tenant_id) REFERENCES public.accounts(id, tenant_id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: transactions transactions_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE SET NULL;


--
-- Name: transactions transactions_category_id_tenant_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_tenant_fk FOREIGN KEY (category_id, category_tenant_id) REFERENCES public.categories(id, tenant_id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: transactions transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users Users can insert own data; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Users can insert own data" ON public.users FOR INSERT WITH CHECK (true);


--
-- Name: users Users can update own data; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Users can update own data" ON public.users FOR UPDATE USING (true);


--
-- Name: users Users can view own data; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Users can view own data" ON public.users FOR SELECT USING (true);


--
-- Name: accounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: accounts accounts_tenant_policy_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY accounts_tenant_policy_delete ON public.accounts FOR DELETE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: accounts accounts_tenant_policy_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY accounts_tenant_policy_insert ON public.accounts FOR INSERT WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: accounts accounts_tenant_policy_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY accounts_tenant_policy_select ON public.accounts FOR SELECT USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: accounts accounts_tenant_policy_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY accounts_tenant_policy_update ON public.accounts FOR UPDATE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: categories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;

--
-- Name: categories categories_tenant_policy_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY categories_tenant_policy_delete ON public.categories FOR DELETE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: categories categories_tenant_policy_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY categories_tenant_policy_insert ON public.categories FOR INSERT WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: categories categories_tenant_policy_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY categories_tenant_policy_select ON public.categories FOR SELECT USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: categories categories_tenant_policy_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY categories_tenant_policy_update ON public.categories FOR UPDATE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: oauth_states; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

--
-- Name: tenant_members; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_members ENABLE ROW LEVEL SECURITY;

--
-- Name: tenants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

--
-- Name: transactions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

--
-- Name: transactions transactions_tenant_policy_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY transactions_tenant_policy_delete ON public.transactions FOR DELETE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: transactions transactions_tenant_policy_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY transactions_tenant_policy_insert ON public.transactions FOR INSERT WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: transactions transactions_tenant_policy_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY transactions_tenant_policy_select ON public.transactions FOR SELECT USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: transactions transactions_tenant_policy_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY transactions_tenant_policy_update ON public.transactions FOR UPDATE USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()) AND (auth.uid() = user_id)));


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: users users_select_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY users_select_own ON public.users FOR SELECT USING ((id = public.current_app_user_id()));


--
-- Name: users users_update_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY users_update_own ON public.users FOR UPDATE USING ((id = public.current_app_user_id())) WITH CHECK ((id = public.current_app_user_id()));


--
-- PostgreSQL database dump complete
--

\unrestrict o0kL7X6UkD8n3cDTm2M5KNqssHEDHrcos94VtbXdXoS4R8f6ekYRJtR7Ly9MK4Z



-- =============================================
-- FUNCTIONS
-- =============================================

 schema |           name           |                                                   definition                                                   
--------+--------------------------+----------------------------------------------------------------------------------------------------------------
 public | current_app_user_id      | CREATE OR REPLACE FUNCTION public.current_app_user_id()                                                       +
        |                          |  RETURNS uuid                                                                                                 +
        |                          |  LANGUAGE sql                                                                                                 +
        |                          |  STABLE                                                                                                       +
        |                          | AS $function$                                                                                                 +
        |                          |   SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid;                                      +
        |                          | $function$                                                                                                    +
        |                          | 
 public | current_tenant_id        | CREATE OR REPLACE FUNCTION public.current_tenant_id()                                                         +
        |                          |  RETURNS uuid                                                                                                 +
        |                          |  LANGUAGE sql                                                                                                 +
        |                          |  STABLE                                                                                                       +
        |                          | AS $function$                                                                                                 +
        |                          |   SELECT COALESCE(                                                                                            +
        |                          |     NULLIF(current_setting('request.jwt.claim.tenant_id', true), '')::uuid,                                   +
        |                          |     NULLIF(current_setting('app.current_tenant_id', true), '')::uuid                                          +
        |                          |   );                                                                                                          +
        |                          | $function$                                                                                                    +
        |                          | 
 public | dev_seed_account         | CREATE OR REPLACE FUNCTION public.dev_seed_account(p_name text, p_type text, p_user_id uuid, p_tenant_id uuid)+
        |                          |  RETURNS accounts                                                                                             +
        |                          |  LANGUAGE plpgsql                                                                                             +
        |                          |  SECURITY DEFINER                                                                                             +
        |                          |  SET search_path TO 'public'                                                                                  +
        |                          | AS $function$                                                                                                 +
        |                          | declare                                                                                                       +
        |                          |   v_row public.accounts;                                                                                      +
        |                          | begin                                                                                                         +
        |                          |   insert into public.accounts (name, type, user_id, tenant_id)                                                +
        |                          |   values (p_name, p_type, p_user_id, p_tenant_id)                                                             +
        |                          |   returning * into v_row;                                                                                     +
        |                          |                                                                                                               +
        |                          |   return v_row;                                                                                               +
        |                          | end;                                                                                                          +
        |                          | $function$                                                                                                    +
        |                          | 
 public | update_updated_at_column | CREATE OR REPLACE FUNCTION public.update_updated_at_column()                                                  +
        |                          |  RETURNS trigger                                                                                              +
        |                          |  LANGUAGE plpgsql                                                                                             +
        |                          | AS $function$                                                                                                 +
        |                          | BEGIN                                                                                                         +
        |                          |     NEW.updated_at = NOW();                                                                                   +
        |                          |     RETURN NEW;                                                                                               +
        |                          | END;                                                                                                          +
        |                          | $function$                                                                                                    +
        |                          | 
(4 rows)



-- =============================================
-- TRIGGERS (INFO)
-- =============================================

    table     |          trigger_name          | action_timing | event_manipulation |              action_statement               
--------------+--------------------------------+---------------+--------------------+---------------------------------------------
 accounts     | update_accounts_updated_at     | BEFORE        | UPDATE             | EXECUTE FUNCTION update_updated_at_column()
 categories   | update_categories_updated_at   | BEFORE        | UPDATE             | EXECUTE FUNCTION update_updated_at_column()
 transactions | update_transactions_updated_at | BEFORE        | UPDATE             | EXECUTE FUNCTION update_updated_at_column()
 users        | update_users_updated_at        | BEFORE        | UPDATE             | EXECUTE FUNCTION update_updated_at_column()
(4 rows)



-- =============================================
-- CONSTRAINTS (INFO)
-- =============================================

   table_name   |           constraint_name            | contype |                                                                               definition                                                                                
----------------+--------------------------------------+---------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 users          | users_email_key                      | u       | UNIQUE (email)
 users          | users_pkey                           | p       | PRIMARY KEY (id)
 categories     | categories_id_tenant_unique          | u       | UNIQUE (id, tenant_id)
 categories     | categories_pkey                      | p       | PRIMARY KEY (id)
 categories     | categories_type_check                | c       | CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
 categories     | categories_user_id_fkey              | f       | FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
 accounts       | accounts_account_id_fkey             | f       | FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
 accounts       | accounts_id_tenant_unique            | u       | UNIQUE (id, tenant_id)
 accounts       | accounts_pkey                        | p       | PRIMARY KEY (id)
 accounts       | accounts_user_id_fkey                | f       | FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
 transactions   | transactions_account_id_fkey         | f       | FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
 transactions   | transactions_account_id_tenant_fk    | f       | FOREIGN KEY (account_id, account_tenant_id) REFERENCES accounts(id, tenant_id) ON UPDATE RESTRICT ON DELETE RESTRICT
 transactions   | transactions_account_tenant_matches  | c       | CHECK ((account_tenant_id = tenant_id))
 transactions   | transactions_category_id_fkey        | f       | FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
 transactions   | transactions_category_id_tenant_fk   | f       | FOREIGN KEY (category_id, category_tenant_id) REFERENCES categories(id, tenant_id) ON UPDATE RESTRICT ON DELETE RESTRICT
 transactions   | transactions_category_tenant_matches | c       | CHECK ((category_tenant_id = tenant_id))
 transactions   | transactions_pkey                    | p       | PRIMARY KEY (id)
 transactions   | transactions_status_check            | c       | CHECK (((status)::text = ANY ((ARRAY['paid'::character varying, 'pending'::character varying, 'overdue'::character varying, 'cancelled'::character varying])::text[])))
 transactions   | transactions_type_check              | c       | CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying])::text[])))
 transactions   | transactions_user_id_fkey            | f       | FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
 oauth_states   | oauth_states_pkey                    | p       | PRIMARY KEY (id)
 oauth_states   | oauth_states_state_key               | u       | UNIQUE (state)
 tenants        | tenants_pkey                         | p       | PRIMARY KEY (id)
 tenants        | tenants_slug_key                     | u       | UNIQUE (slug)
 tenant_members | tenant_members_pkey                  | p       | PRIMARY KEY (id)
 tenant_members | tenant_members_role_check            | c       | CHECK ((role = ANY (ARRAY['owner'::text, 'admin'::text, 'member'::text, 'viewer'::text])))
 tenant_members | tenant_members_tenant_id_fkey        | f       | FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
 tenant_members | tenant_members_tenant_user_unique    | u       | UNIQUE (tenant_id, user_id)
 tenant_members | tenant_members_user_id_fkey          | f       | FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
(29 rows)



-- =============================================
-- INDEXES (INFO)
-- =============================================

 schemaname |   tablename    |             indexname             |                                                     indexdef                                                      
------------+----------------+-----------------------------------+-------------------------------------------------------------------------------------------------------------------
 public     | accounts       | accounts_id_tenant_unique         | CREATE UNIQUE INDEX accounts_id_tenant_unique ON public.accounts USING btree (id, tenant_id)
 public     | accounts       | accounts_pkey                     | CREATE UNIQUE INDEX accounts_pkey ON public.accounts USING btree (id)
 public     | accounts       | idx_accounts_active               | CREATE INDEX idx_accounts_active ON public.accounts USING btree (active)
 public     | accounts       | idx_accounts_tenant_user          | CREATE INDEX idx_accounts_tenant_user ON public.accounts USING btree (tenant_id, user_id)
 public     | accounts       | idx_accounts_user_id              | CREATE INDEX idx_accounts_user_id ON public.accounts USING btree (user_id)
 public     | categories     | categories_id_tenant_unique       | CREATE UNIQUE INDEX categories_id_tenant_unique ON public.categories USING btree (id, tenant_id)
 public     | categories     | categories_pkey                   | CREATE UNIQUE INDEX categories_pkey ON public.categories USING btree (id)
 public     | categories     | idx_categories_active             | CREATE INDEX idx_categories_active ON public.categories USING btree (active)
 public     | categories     | idx_categories_tenant_user        | CREATE INDEX idx_categories_tenant_user ON public.categories USING btree (tenant_id, user_id)
 public     | categories     | idx_categories_type               | CREATE INDEX idx_categories_type ON public.categories USING btree (type)
 public     | categories     | idx_categories_user_id            | CREATE INDEX idx_categories_user_id ON public.categories USING btree (user_id)
 public     | oauth_states   | idx_oauth_states_expires_at       | CREATE INDEX idx_oauth_states_expires_at ON public.oauth_states USING btree (expires_at)
 public     | oauth_states   | idx_oauth_states_state            | CREATE INDEX idx_oauth_states_state ON public.oauth_states USING btree (state)
 public     | oauth_states   | oauth_states_pkey                 | CREATE UNIQUE INDEX oauth_states_pkey ON public.oauth_states USING btree (id)
 public     | oauth_states   | oauth_states_state_key            | CREATE UNIQUE INDEX oauth_states_state_key ON public.oauth_states USING btree (state)
 public     | tenant_members | idx_tenant_members_tenant_id      | CREATE INDEX idx_tenant_members_tenant_id ON public.tenant_members USING btree (tenant_id)
 public     | tenant_members | idx_tenant_members_user_id        | CREATE INDEX idx_tenant_members_user_id ON public.tenant_members USING btree (user_id)
 public     | tenant_members | tenant_members_pkey               | CREATE UNIQUE INDEX tenant_members_pkey ON public.tenant_members USING btree (id)
 public     | tenant_members | tenant_members_tenant_user_unique | CREATE UNIQUE INDEX tenant_members_tenant_user_unique ON public.tenant_members USING btree (tenant_id, user_id)
 public     | tenants        | tenants_pkey                      | CREATE UNIQUE INDEX tenants_pkey ON public.tenants USING btree (id)
 public     | tenants        | tenants_slug_key                  | CREATE UNIQUE INDEX tenants_slug_key ON public.tenants USING btree (slug)
 public     | transactions   | idx_transactions_account_id       | CREATE INDEX idx_transactions_account_id ON public.transactions USING btree (account_id)
 public     | transactions   | idx_transactions_category_id      | CREATE INDEX idx_transactions_category_id ON public.transactions USING btree (category_id)
 public     | transactions   | idx_transactions_date             | CREATE INDEX idx_transactions_date ON public.transactions USING btree (date)
 public     | transactions   | idx_transactions_status           | CREATE INDEX idx_transactions_status ON public.transactions USING btree (status)
 public     | transactions   | idx_transactions_tenant_user_date | CREATE INDEX idx_transactions_tenant_user_date ON public.transactions USING btree (tenant_id, user_id, date DESC)
 public     | transactions   | idx_transactions_type             | CREATE INDEX idx_transactions_type ON public.transactions USING btree (type)
 public     | transactions   | idx_transactions_user_date        | CREATE INDEX idx_transactions_user_date ON public.transactions USING btree (user_id, date DESC)
 public     | transactions   | idx_transactions_user_id          | CREATE INDEX idx_transactions_user_id ON public.transactions USING btree (user_id)
 public     | transactions   | transactions_pkey                 | CREATE UNIQUE INDEX transactions_pkey ON public.transactions USING btree (id)
 public     | users          | idx_users_created_at              | CREATE INDEX idx_users_created_at ON public.users USING btree (created_at)
 public     | users          | idx_users_email                   | CREATE INDEX idx_users_email ON public.users USING btree (email)
 public     | users          | users_email_key                   | CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)
 public     | users          | users_pkey                        | CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)
(34 rows)



-- =============================================
-- RLS POLICIES
-- =============================================

                                                                                                                                                   ddl                                                                                                                                                   
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 CREATE POLICY accounts_tenant_policy_delete ON public.accounts FOR DELETE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY accounts_tenant_policy_insert ON public.accounts FOR INSERT TO public WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY accounts_tenant_policy_select ON public.accounts FOR SELECT TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY accounts_tenant_policy_update ON public.accounts FOR UPDATE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY categories_tenant_policy_delete ON public.categories FOR DELETE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY categories_tenant_policy_insert ON public.categories FOR INSERT TO public WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY categories_tenant_policy_select ON public.categories FOR SELECT TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY categories_tenant_policy_update ON public.categories FOR UPDATE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY transactions_tenant_policy_delete ON public.transactions FOR DELETE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY transactions_tenant_policy_insert ON public.transactions FOR INSERT TO public WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY transactions_tenant_policy_select ON public.transactions FOR SELECT TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) ;
 CREATE POLICY transactions_tenant_policy_update ON public.transactions FOR UPDATE TO public USING (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id))) WITH CHECK (((tenant_id IS NOT NULL) AND (tenant_id = current_tenant_id()) AND (auth.uid() = user_id)));
 CREATE POLICY "Users can insert own data" ON public.users FOR INSERT TO public WITH CHECK (true);
 CREATE POLICY "Users can update own data" ON public.users FOR UPDATE TO public USING (true) ;
 CREATE POLICY "Users can view own data" ON public.users FOR SELECT TO public USING (true) ;
 CREATE POLICY users_select_own ON public.users FOR SELECT TO public USING ((id = current_app_user_id())) ;
 CREATE POLICY users_update_own ON public.users FOR UPDATE TO public USING ((id = current_app_user_id())) WITH CHECK ((id = current_app_user_id()));
(17 rows)



-- =============================================
-- TRIGGERS (DDL)
-- =============================================

                                                                  ddl                                                                  
---------------------------------------------------------------------------------------------------------------------------------------
 CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
 CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
 CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
 CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
(4 rows)

