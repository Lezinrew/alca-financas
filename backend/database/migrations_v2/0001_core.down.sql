BEGIN;

DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS payable_payments;
DROP TABLE IF EXISTS payables;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS import_batches;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS tenant_members;
DROP TABLE IF EXISTS tenants;
DROP TABLE IF EXISTS password_reset_tokens;
DROP TABLE IF EXISTS auth_sessions;
DROP TABLE IF EXISTS users;
DROP FUNCTION IF EXISTS set_updated_at();

COMMIT;

