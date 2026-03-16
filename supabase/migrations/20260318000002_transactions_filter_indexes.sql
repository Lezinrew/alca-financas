-- Índices para melhorar performance de filtros em transactions

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

CREATE INDEX IF NOT EXISTS idx_transactions_user_date
  ON public.transactions (user_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_user_category
  ON public.transactions (user_id, category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_user_account
  ON public.transactions (user_id, account_id);

CREATE INDEX IF NOT EXISTS idx_transactions_user_type
  ON public.transactions (user_id, type);

CREATE INDEX IF NOT EXISTS idx_transactions_user_amount
  ON public.transactions (user_id, amount);

-- Opcional: método de pagamento, se existir no schema
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'transactions'
      AND column_name = 'method'
  ) THEN
    CREATE INDEX IF NOT EXISTS idx_transactions_user_method
      ON public.transactions (user_id, method);
  END IF;
END $$;

COMMIT;

