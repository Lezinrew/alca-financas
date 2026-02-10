-- Definir senha do usuário lezinrew@gmail.com para: 1234mudar
-- Execute no SQL Editor do Supabase (Project > SQL Editor)
-- A coluna password é BYTEA (hash bcrypt).

UPDATE users
SET
  password = decode('243262243132242e3576354e524632474a6c6e374f6174586b5a76376579485370443763785a6f656374696c614e2f4f67456246305634763150554b', 'hex'),
  updated_at = NOW()
WHERE LOWER(TRIM(email)) = 'lezinrew@gmail.com';

-- Verificar se atualizou (deve retornar 1 linha)
-- SELECT id, email, name, updated_at FROM users WHERE LOWER(email) = 'lezinrew@gmail.com';
