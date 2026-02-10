-- 1) Ver usuários e e-mails na tabela (rode primeiro para conferir)
SELECT id, email, name, created_at
FROM users
ORDER BY created_at DESC;

-- 2) Se lezinrew@gmail.com NÃO aparecer, crie o usuário e já defina a senha:
-- INSERT INTO users (id, email, name, password, settings, auth_providers, is_admin)
-- VALUES (
--   gen_random_uuid(),
--   'lezinrew@gmail.com',
--   'Lezinrew',
--   decode('243262243132242e3576354e524632474a6c6e374f6174586b5a76376579485370443763785a6f656374696c614e2f4f67456246305634763150554b', 'hex'),
--   '{"currency": "BRL", "theme": "light", "language": "pt"}'::jsonb,
--   '[]'::jsonb,
--   FALSE
-- );

-- 3) Se o e-mail existir com outro formato (ex.: maiúsculas), use o UPDATE abaixo
--    trocando pelo e-mail exato que apareceu no SELECT:
-- UPDATE users
-- SET
--   password = decode('243262243132242e3576354e524632474a6c6e374f6174586b5a76376579485370443763785a6f656374696c614e2f4f67456246305634763150554b', 'hex'),
--   updated_at = NOW()
-- WHERE email = 'LEZINREW@GMAIL.COM';  -- use o valor exato do SELECT
