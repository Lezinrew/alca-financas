-- Plataforma de IA (contrato docs/contracts/ai-platform-v1.md).
-- Somente PostgreSQL V2 próprio. NÃO executar no Supabase.
-- Depende de 0001_core.sql. Reversão: 0002_ai_platform.down.sql.
BEGIN;

-- ---------------------------------------------------------------------------
-- Escopo por tenant para RLS.
-- O serviço define app.tenant_id no início de cada transação (SET LOCAL via
-- set_config). Sem valor definido, nenhuma linha é visível.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ai_current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

-- ---------------------------------------------------------------------------
-- Espaços financeiros: pessoal, família e negócio dentro de um tenant.
-- Tabelas de vínculo evitam alterar accounts/payables criadas em 0001.
-- ---------------------------------------------------------------------------
CREATE TABLE financial_spaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('personal', 'family', 'business')),
    name text NOT NULL CHECK (length(trim(name)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz,
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, name)
);

CREATE TRIGGER financial_spaces_set_updated_at
BEFORE UPDATE ON financial_spaces
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE financial_space_members (
    tenant_id uuid NOT NULL,
    financial_space_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'member', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (financial_space_id, user_id),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, user_id)
        REFERENCES tenant_members(tenant_id, user_id) ON DELETE RESTRICT
);

CREATE INDEX financial_space_members_user_idx
    ON financial_space_members (user_id, tenant_id);

-- Uma conta pertence a no máximo um espaço. Conta sem vínculo fica fora do
-- alcance da IA: ausência de vínculo nunca significa acesso amplo.
CREATE TABLE financial_space_accounts (
    account_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    financial_space_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id, tenant_id)
        REFERENCES accounts(id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX financial_space_accounts_space_idx
    ON financial_space_accounts (tenant_id, financial_space_id);

CREATE TABLE financial_space_payables (
    payable_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    financial_space_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (payable_id, tenant_id)
        REFERENCES payables(id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX financial_space_payables_space_idx
    ON financial_space_payables (tenant_id, financial_space_id);

-- ---------------------------------------------------------------------------
-- Autorizações permanentes (grants): revogáveis, com escopo e versão.
-- Um grant vale para um espaço financeiro.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    granted_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    profile text NOT NULL DEFAULT 'owner_operator'
        CHECK (profile IN ('owner_operator')),
    mode text NOT NULL CHECK (mode IN ('observe', 'assisted', 'delegated')),
    capabilities text[] NOT NULL CHECK (cardinality(capabilities) > 0),
    account_ids uuid[],
    amount_limit numeric(19,2) CHECK (amount_limit IS NULL OR amount_limit > 0),
    amount_unlimited boolean NOT NULL DEFAULT false,
    period_start date,
    period_end date,
    allowed_sources text[],
    policy_version integer NOT NULL DEFAULT 1 CHECK (policy_version > 0),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_until timestamptz,
    revoked_at timestamptz,
    revoked_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    revocation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    -- Limite de valor é decisão explícita: ou há teto, ou é declarado ilimitado.
    CHECK (NOT (amount_unlimited AND amount_limit IS NOT NULL)),
    CHECK (mode <> 'delegated' OR amount_unlimited OR amount_limit IS NOT NULL),
    CHECK (period_start IS NULL OR period_end IS NULL OR period_end >= period_start),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    CHECK (account_ids IS NULL OR cardinality(account_ids) > 0),
    CHECK (allowed_sources IS NULL OR cardinality(allowed_sources) > 0)
);

CREATE INDEX ai_grants_actor_active_idx
    ON ai_grants (tenant_id, actor_user_id, financial_space_id)
    WHERE revoked_at IS NULL;

CREATE TRIGGER ai_grants_set_updated_at
BEFORE UPDATE ON ai_grants
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Execuções, checkpoints e fila com lease.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    -- Guarda "origem:sha256" da chave recebida, nunca a chave crua do cliente.
    idempotency_key text CHECK (idempotency_key IS NULL OR length(idempotency_key) BETWEEN 8 AND 200),
    request_hash text NOT NULL CHECK (length(request_hash) = 64),
    contract_version text NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    channel text NOT NULL CHECK (channel IN ('web', 'whatsapp', 'worker')),
    locale text NOT NULL DEFAULT 'pt-BR',
    timezone text NOT NULL DEFAULT 'America/Sao_Paulo',
    task text NOT NULL CHECK (task IN (
        'finance_question', 'statement_import', 'apply_proposal', 'reverse_operation'
    )),
    privacy text NOT NULL CHECK (privacy IN ('local_only', 'cloud_redacted', 'cloud_allowed')),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'waiting_review', 'completed',
        'failed', 'cancelled', 'needs_reconciliation'
    )),
    -- Pedido do titular e referências de entrada. Nunca credenciais nem
    -- prompts/respostas brutas de modelo.
    input jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb,
    error jsonb,
    model_alias text,
    model_provider text,
    model_id text,
    fallback_used boolean NOT NULL DEFAULT false,
    inference_calls integer NOT NULL DEFAULT 0 CHECK (inference_calls >= 0),
    tool_calls integer NOT NULL DEFAULT 0 CHECK (tool_calls >= 0),
    cost_micros bigint NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    cost_currency char(3),
    lease_owner text,
    lease_expires_at timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    cancel_requested_at timestamptz,
    deadline_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    UNIQUE (id, tenant_id),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);

CREATE UNIQUE INDEX ai_runs_idempotency_unique
    ON ai_runs (tenant_id, actor_user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX ai_runs_queue_idx
    ON ai_runs (created_at)
    WHERE status IN ('queued', 'running');
CREATE INDEX ai_runs_actor_created_idx
    ON ai_runs (tenant_id, actor_user_id, created_at DESC);

CREATE TRIGGER ai_runs_set_updated_at
BEFORE UPDATE ON ai_runs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Checkpoint durável de cada etapa. step_key é a identidade estável da etapa:
-- uma etapa concluída nunca é reexecutada após reinício ou troca de provedor.
CREATE TABLE ai_run_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    seq integer NOT NULL CHECK (seq > 0),
    step_key text NOT NULL CHECK (length(step_key) BETWEEN 1 AND 300),
    kind text NOT NULL CHECK (kind IN ('inference', 'tool')),
    name text NOT NULL,
    version text,
    status text NOT NULL CHECK (status IN ('started', 'succeeded', 'failed')),
    args_hash text,
    output jsonb,
    error_code text,
    attempts integer NOT NULL DEFAULT 1 CHECK (attempts > 0),
    duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
    cost_micros bigint NOT NULL DEFAULT 0 CHECK (cost_micros >= 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (run_id, seq),
    UNIQUE (run_id, step_key),
    FOREIGN KEY (run_id, tenant_id)
        REFERENCES ai_runs(id, tenant_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- E-mail: vínculo OAuth (somente referência à credencial) e quarentena.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_email_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    provider text NOT NULL CHECK (length(trim(provider)) > 0),
    mailbox_label text NOT NULL CHECK (length(trim(mailbox_label)) > 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'revoked', 'error')),
    -- Referência opaca ao cofre de credenciais. O token OAuth nunca é
    -- armazenado nesta tabela nem entregue ao modelo.
    credential_ref text,
    scopes text[] NOT NULL DEFAULT '{}',
    last_error_code text,
    connected_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    CHECK ((status = 'revoked') = (revoked_at IS NOT NULL))
);

CREATE TRIGGER ai_email_connections_set_updated_at
BEFORE UPDATE ON ai_email_connections
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- No máximo uma caixa postal ativa por titular em cada espaço.
CREATE UNIQUE INDEX ai_email_connections_one_active_unique
    ON ai_email_connections (tenant_id, financial_space_id, owner_user_id)
    WHERE status = 'active';

CREATE TABLE ai_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    run_id uuid,
    connection_id uuid,
    source_kind text NOT NULL CHECK (source_kind IN ('email', 'upload', 'whatsapp')),
    source_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
    original_filename text NOT NULL CHECK (length(trim(original_filename)) > 0),
    declared_mime text,
    detected_kind text NOT NULL
        CHECK (detected_kind IN ('ofx', 'csv', 'pdf', 'png', 'jpeg')),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 20971520),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    storage_key text NOT NULL,
    state text NOT NULL DEFAULT 'quarantined'
        CHECK (state IN ('quarantined', 'previewed', 'consumed', 'expired')),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    -- Deduplicação por arquivo dentro do espaço.
    UNIQUE (tenant_id, financial_space_id, sha256),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (connection_id, tenant_id)
        REFERENCES ai_email_connections(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (run_id, tenant_id)
        REFERENCES ai_runs(id, tenant_id) ON DELETE SET NULL (run_id)
);

-- ---------------------------------------------------------------------------
-- Propostas, operações idempotentes e outbox.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    run_id uuid,
    kind text NOT NULL CHECK (kind IN (
        'payable_payment', 'statement_import', 'reverse_operation'
    )),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'ready', 'approved', 'applied', 'rejected', 'expired', 'stale'
    )),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    target_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
    expected_effect jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    ambiguities jsonb NOT NULL DEFAULT '[]'::jsonb,
    requires_review boolean NOT NULL DEFAULT false,
    -- Chave produzida pelo backend (escopo + fonte + tipo + identidade da ação).
    operation_key text NOT NULL CHECK (operation_key ~ '^[0-9a-f]{64}$'),
    approval_kind text CHECK (approval_kind IN ('specific', 'grant')),
    approved_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    approved_grant_id uuid,
    approved_grant_version integer,
    approved_hash text,
    approved_at timestamptz,
    rejected_reason text,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, tenant_id),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (run_id, tenant_id)
        REFERENCES ai_runs(id, tenant_id) ON DELETE SET NULL (run_id),
    FOREIGN KEY (approved_grant_id, tenant_id)
        REFERENCES ai_grants(id, tenant_id) ON DELETE RESTRICT,
    CHECK (
        (status IN ('approved', 'applied')) <= (approval_kind IS NOT NULL AND approved_at IS NOT NULL)
    ),
    CHECK (approval_kind IS NULL OR approved_hash = payload_hash),
    CHECK (approval_kind <> 'grant' OR approved_grant_id IS NOT NULL),
    CHECK (approval_kind <> 'specific' OR approved_by_user_id IS NOT NULL)
);

-- Uma única proposta viva por ação.
CREATE UNIQUE INDEX ai_proposals_live_operation_key_unique
    ON ai_proposals (tenant_id, operation_key)
    WHERE status IN ('draft', 'ready', 'approved');
CREATE INDEX ai_proposals_space_status_idx
    ON ai_proposals (tenant_id, financial_space_id, status, created_at DESC);

CREATE TRIGGER ai_proposals_set_updated_at
BEFORE UPDATE ON ai_proposals
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A linha de operação nasce na MESMA transação do efeito financeiro, da
-- auditoria e do outbox. O índice único é a barreira final contra efeito
-- duplicado entre workers, reenvios e troca de provedor.
CREATE TABLE ai_operations (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    run_id uuid,
    actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    grant_id uuid,
    kind text NOT NULL CHECK (kind IN (
        'payable_payment', 'statement_import', 'reverse_operation'
    )),
    operation_key text NOT NULL CHECK (operation_key ~ '^[0-9a-f]{64}$'),
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'applied' CHECK (status IN ('applied', 'reversed')),
    effect jsonb NOT NULL DEFAULT '{}'::jsonb,
    reverses_operation_id uuid,
    reversed_by_operation_id uuid,
    applied_at timestamptz NOT NULL DEFAULT now(),
    reversed_at timestamptz,
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, operation_key),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (proposal_id, tenant_id)
        REFERENCES ai_proposals(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (grant_id, tenant_id)
        REFERENCES ai_grants(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (reverses_operation_id, tenant_id)
        REFERENCES ai_operations(id, tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (reversed_by_operation_id, tenant_id)
        REFERENCES ai_operations(id, tenant_id) ON DELETE RESTRICT,
    CHECK ((status = 'reversed') = (reversed_at IS NOT NULL)),
    CHECK ((status = 'reversed') = (reversed_by_operation_id IS NOT NULL))
);

CREATE UNIQUE INDEX ai_operations_single_reversal_unique
    ON ai_operations (tenant_id, reverses_operation_id)
    WHERE reverses_operation_id IS NOT NULL;
CREATE INDEX ai_operations_proposal_idx
    ON ai_operations (tenant_id, proposal_id);

CREATE TABLE ai_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    operation_id uuid,
    run_id uuid,
    topic text NOT NULL CHECK (length(trim(topic)) > 0),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- O consumidor deduplica por esta chave; reentrega nunca refaz o efeito.
    dedup_key text NOT NULL CHECK (length(dedup_key) BETWEEN 8 AND 200),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'delivered', 'failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error_code text,
    available_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, dedup_key),
    FOREIGN KEY (operation_id, tenant_id)
        REFERENCES ai_operations(id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX ai_outbox_pending_idx
    ON ai_outbox (available_at)
    WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- Orçamento: teto por execução, dia e mês, com reserva atômica.
-- Zero impede gasto externo. Valores em micros da moeda declarada.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_budget_limits (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE RESTRICT,
    currency char(3) NOT NULL CHECK (currency = upper(currency)),
    per_run_micros bigint NOT NULL DEFAULT 0 CHECK (per_run_micros >= 0),
    per_day_micros bigint NOT NULL DEFAULT 0 CHECK (per_day_micros >= 0),
    per_month_micros bigint NOT NULL DEFAULT 0 CHECK (per_month_micros >= 0),
    updated_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_budget_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    run_id uuid,
    route_alias text NOT NULL,
    currency char(3) NOT NULL CHECK (currency = upper(currency)),
    reserved_micros bigint NOT NULL CHECK (reserved_micros >= 0),
    actual_micros bigint CHECK (actual_micros IS NULL OR actual_micros >= 0),
    status text NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'reconciled', 'released')),
    budget_day date NOT NULL,
    budget_month date NOT NULL
        CHECK (budget_month = date_trunc('month', budget_month)::date),
    created_at timestamptz NOT NULL DEFAULT now(),
    settled_at timestamptz,
    CHECK ((status = 'reserved') = (settled_at IS NULL)),
    CHECK (status <> 'reconciled' OR actual_micros IS NOT NULL)
);

CREATE INDEX ai_budget_entries_period_idx
    ON ai_budget_entries (tenant_id, budget_month, budget_day);
CREATE INDEX ai_budget_entries_run_idx
    ON ai_budget_entries (tenant_id, run_id);

-- ---------------------------------------------------------------------------
-- RAG pessoal: trechos com tenant, espaço, ACL, fonte, hash, versão e datas.
-- Busca lexical em português; números financeiros não saem daqui.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_rag_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    financial_space_id uuid NOT NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    source_kind text NOT NULL CHECK (source_kind IN ('note', 'rule', 'artifact', 'import')),
    source_ref text NOT NULL,
    title text NOT NULL CHECK (length(trim(title)) > 0),
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    -- NULL = todos os membros do espaço; lista = somente os usuários citados.
    acl_user_ids uuid[],
    document_date date,
    indexed_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, financial_space_id, source_ref, version),
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT,
    CHECK (acl_user_ids IS NULL OR cardinality(acl_user_ids) > 0)
);

CREATE TABLE ai_rag_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    financial_space_id uuid NOT NULL,
    document_id uuid NOT NULL,
    seq integer NOT NULL CHECK (seq >= 0),
    content text NOT NULL CHECK (length(content) > 0),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', content)) STORED,
    UNIQUE (document_id, seq),
    FOREIGN KEY (document_id, tenant_id)
        REFERENCES ai_rag_documents(id, tenant_id) ON DELETE CASCADE,
    FOREIGN KEY (financial_space_id, tenant_id)
        REFERENCES financial_spaces(id, tenant_id) ON DELETE RESTRICT
);

CREATE INDEX ai_rag_chunks_tsv_idx ON ai_rag_chunks USING gin (tsv);
CREATE INDEX ai_rag_chunks_space_idx ON ai_rag_chunks (tenant_id, financial_space_id);

-- ---------------------------------------------------------------------------
-- RLS complementar à validação no serviço.
-- FORCE faz a política valer também para o dono das tabelas. Atenção: papéis
-- SUPERUSER ou BYPASSRLS ignoram RLS; a aplicação deve conectar com um papel
-- comum (ver docs/runbooks/ai-platform.md).
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    scoped_table text;
BEGIN
    FOREACH scoped_table IN ARRAY ARRAY[
        'financial_spaces', 'financial_space_members', 'financial_space_accounts',
        'financial_space_payables', 'ai_grants', 'ai_runs', 'ai_run_steps',
        'ai_email_connections', 'ai_artifacts', 'ai_proposals', 'ai_operations',
        'ai_outbox', 'ai_budget_limits', 'ai_budget_entries',
        'ai_rag_documents', 'ai_rag_chunks'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', scoped_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', scoped_table);
        EXECUTE format(
            'CREATE POLICY %I ON %I USING (tenant_id = ai_current_tenant_id()) '
            'WITH CHECK (tenant_id = ai_current_tenant_id())',
            scoped_table || '_tenant_isolation', scoped_table
        );
    END LOOP;
END;
$$;

-- A fila precisa descobrir execuções e entregas pendentes de qualquer tenant.
-- Só as tabelas de fila aceitam esse modo, restrito a linhas ainda pendentes;
-- depois de assumir uma execução, o worker passa a operar no escopo do tenant.
CREATE POLICY ai_runs_queue_claim ON ai_runs
    USING (
        current_setting('app.ai_queue', true) = 'on'
        AND status IN ('queued', 'running')
    )
    WITH CHECK (current_setting('app.ai_queue', true) = 'on');

CREATE POLICY ai_outbox_queue_claim ON ai_outbox
    USING (
        current_setting('app.ai_queue', true) = 'on'
        AND status = 'pending'
    )
    WITH CHECK (current_setting('app.ai_queue', true) = 'on');

COMMIT;
