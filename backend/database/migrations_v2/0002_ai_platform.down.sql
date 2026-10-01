-- Reverte 0002_ai_platform.sql. Remove estado da plataforma de IA
-- (execuções, propostas, operações, outbox, grants, quarentena e RAG).
-- NÃO desfaz efeitos financeiros já aplicados em payable_payments/transactions:
-- esses permanecem em 0001 e devem ser revertidos por compensação antes.
-- Use somente em banco local/descartável ou após exportar ai_operations e
-- audit_events, conforme docs/runbooks/ai-platform.md.
BEGIN;

DROP TABLE IF EXISTS ai_rag_chunks;
DROP TABLE IF EXISTS ai_rag_documents;
DROP TABLE IF EXISTS ai_budget_entries;
DROP TABLE IF EXISTS ai_budget_limits;
DROP TABLE IF EXISTS ai_outbox;
DROP TABLE IF EXISTS ai_operations;
DROP TABLE IF EXISTS ai_proposals;
DROP TABLE IF EXISTS ai_artifacts;
DROP TABLE IF EXISTS ai_email_connections;
DROP TABLE IF EXISTS ai_run_steps;
DROP TABLE IF EXISTS ai_runs;
DROP TABLE IF EXISTS ai_grants;
DROP TABLE IF EXISTS financial_space_payables;
DROP TABLE IF EXISTS financial_space_accounts;
DROP TABLE IF EXISTS financial_space_members;
DROP TABLE IF EXISTS financial_spaces;
DROP FUNCTION IF EXISTS ai_current_tenant_id();

COMMIT;
