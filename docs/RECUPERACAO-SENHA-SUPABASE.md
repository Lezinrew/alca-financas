# Configurar recuperação de senha (Supabase + app)

O app usa **recuperação de senha própria** (backend Flask envia o e-mail com link). O Supabase é o banco de dados; a tela **URL Configuration** do Supabase serve para deixar as URLs alinhadas e para uso futuro (ex.: Supabase Auth ou e-mails do Supabase).

## 1. URL Configuration no Supabase

No painel: **Authentication** → **Configuration** → **URL Configuration**.

### Site URL
- **Valor:** a URL base do seu frontend.
- **Desenvolvimento:** `http://localhost:3000` (ou `http://localhost:5173` se o Vite rodar na 5173).
- **Produção:** `https://seudominio.com.br`.

Deixe como está se já estiver `http://localhost:3000`. Clique em **Save changes** se alterar.

### Redirect URLs
Adicione as URLs para onde o usuário pode ser redirecionado após ações de auth (ex.: depois de redefinir a senha):

| Ambiente   | URL para adicionar              |
|-----------|----------------------------------|
| Local     | `http://localhost:3000/reset-password` |
| Local     | `http://localhost:3000/login`         |
| Local     | `http://localhost:5173/reset-password` (se usar porta 5173) |
| Produção  | `https://seudominio.com.br/reset-password` |
| Produção  | `https://seudominio.com.br/login`       |

1. Clique em **Add URL**.
2. Cole uma URL (ex.: `http://localhost:3000/reset-password`).
3. Adicione as outras da tabela conforme usar (3000, 5173, produção).
4. **Save changes**.

Assim o Supabase aceita redirecionar para a tela de redefinição e para o login do seu app.

---

## 2. Backend: FRONTEND_URL

O link que vai no e-mail de “Esqueci minha senha” é montado no backend com:

`FRONTEND_URL` + `/reset-password?token=...`

Configure no **backend** (`backend/.env`):

```env
# URL do frontend (para link de recuperação de senha no e-mail)
FRONTEND_URL=http://localhost:3000
```

- Em **desenvolvimento** com o script: use `http://localhost:3000` (frontend na porta 3000).
- Se rodar o Vite em outra porta (ex.: 5173), use `http://localhost:5173`.
- Em **produção**: use a URL pública do frontend (ex.: `https://alcahub.com.br`).

Reinicie o backend após alterar o `.env`.

---

## 3. Fluxo atual do app

1. Usuário acessa **Esqueci a senha** e informa o e-mail.
2. Backend gera um token e chama o serviço de e-mail com o link:  
   `FRONTEND_URL/reset-password?token=...`
3. Usuário clica no link e cai na rota `/reset-password` do frontend.
4. Frontend envia o token + nova senha para `POST /api/auth/reset-password`.
5. Backend valida o token e atualiza a senha no Supabase (tabela `users`).

O Supabase **não envia** o e-mail de reset; quem envia é o backend (serviço de e-mail configurado no app). A **URL Configuration** no Supabase garante que, se no futuro você usar redirecionamentos ou e-mails do Supabase Auth, as URLs permitidas já estejam corretas.

---

## 4. Resumo rápido

| Onde              | O que fazer |
|-------------------|-------------|
| Supabase → URL Config | **Site URL:** `http://localhost:3000`. **Redirect URLs:** adicionar `http://localhost:3000/reset-password` e `http://localhost:3000/login`. |
| `backend/.env`    | Definir `FRONTEND_URL=http://localhost:3000` (ou a URL do frontend que você usa). |
| Backend           | Reiniciar após mudar o `.env`. |

Com isso, a tela de recuperação de senha fica alinhada ao Supabase e o link do e-mail aponta para o frontend correto.
