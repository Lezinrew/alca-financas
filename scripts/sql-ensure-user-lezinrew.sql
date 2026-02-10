-- Garante usuário lezinrew@gmail.com com senha 1234mudar
-- Se não existir: cria. Se existir: atualiza a senha.
-- Execute no SQL Editor do Supabase. Depois faça login com 1234mudar.

INSERT INTO users (id, email, name, password, settings, auth_providers, is_admin)
VALUES (
  gen_random_uuid(),
  'lezinrew@gmail.com',
  'Lezinrew',
  decode('243262243132242e3576354e524632474a6c6e374f6174586b5a76376579485370443763785a6f656374696c614e2f4f67456246305634763150554b', 'hex'),
  '{"currency": "BRL", "theme": "light", "language": "pt"}'::jsonb,
  '[]'::jsonb,
  FALSE
)
ON CONFLICT (email) DO UPDATE SET
  password = EXCLUDED.password,
  name = EXCLUDED.name,
  updated_at = NOW();
