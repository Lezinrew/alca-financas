# Contexto: Tela de Login – Estado Atual e O Que Falta

**Última atualização:** fevereiro de 2025

---

## 1. Estado atual da tela de login

### 1.1 Onde está

- **Componente:** `frontend/src/components/auth/Login.tsx`
- **Rota:** `/login` (definida em `App.tsx` dentro de `PublicRoute` – só aparece se o usuário **não** estiver logado).

### 1.2 O que já funciona

| Recurso | Status | Observação |
|--------|--------|------------|
| **Layout** | ✅ | Card central, logo Alça Finanças, gradiente de fundo, dark mode (classes Tailwind). |
| **Formulário email/senha** | ✅ | Campos controlados, validação básica (não enviar vazio), `required` e `autoComplete`. |
| **Mostrar/ocultar senha** | ✅ | Ícone Eye/EyeOff. |
| **Checkbox "Lembrar-me"** | ✅ | Estado no form; **não** persiste sessão (só visual). |
| **Botão Entrar** | ✅ | Loading (Loader2), desabilita durante submit. |
| **Login com email/senha** | ✅ | Chama `login()` do `AuthContext` → `authAPI.login()` → `POST /api/auth/login`. Em sucesso: salva token + user no `localStorage` e redireciona para `/dashboard`. |
| **Exibição de erro** | ✅ | Mensagem do backend (ex.: "Email ou senha incorretos") em caixa vermelha. |
| **Link "Cadastre-se"** | ✅ | Navega para `/register`. |
| **Link "Esqueci a senha"** | ⚠️ | Aponta para `/forgot-password`, mas **não existe rota nem página** para isso (veja seção 3). |
| **Login com Google** | ✅ | Botão chama `oauthAPI.googleLogin()` e redireciona para `GET /api/auth/google/login`. Fluxo OAuth implementado no backend (callback, criação/vinculação de usuário, redirect com token para o frontend). |
| **Microsoft / Apple** | ⚠️ | Botões não existem na UI; na API retornam 501 (não implementado). |

### 1.3 Fluxo técnico do login

1. Usuário preenche email e senha e clica em **Entrar**.
2. `Login.tsx` chama `login({ email, password })` do `AuthContext`.
3. `AuthContext` chama `authAPI.login(credentials)` (`frontend/src/utils/api.ts`).
4. Request: `POST {API_BASE_URL}/api/auth/login` com body `{ email, password }`.  
   - `API_BASE_URL` vem de `VITE_API_URL` ou `REACT_APP_BACKEND_URL` (fallback `http://localhost:8001`).
5. Backend (`backend/routes/auth.py`): valida com `UserLoginSchema`, busca usuário (email case-insensitive), verifica senha com bcrypt, gera JWT e retorna `access_token`, `refresh_token` e `user`.
6. Frontend guarda tokens e `user` no `localStorage` e redireciona para `/dashboard`.
7. Interceptor do Axios envia `Authorization: Bearer <token>` nas próximas requisições; em 401 limpa storage e manda para `/login`.

---

## 2. O que já está pronto no backend

- **POST /api/auth/login** – Login com email/senha (rate limit 5/min).
- **POST /api/auth/register** – Registro (rate limit 3/h).
- **POST /api/auth/refresh** – Renovação de token.
- **GET /api/auth/me** – Dados do usuário (requer token).
- **GET /api/auth/google/login** – Inicia OAuth Google.
- **GET /api/auth/google/callback** – Callback OAuth (redireciona para o frontend com token no HTML que grava no `localStorage`).
- **POST /api/auth/forgot-password** – Aceita `{ email }` e retorna mensagem genérica; **não envia e-mail nem gera link de reset** (veja seção 3).

---

## 3. O que falta para “funcionar por completo”

### 3.1 Esqueci a senha (prioritário)

- **Frontend**
  - **Rota:** Não existe rota `/forgot-password` em `App.tsx`. O link na tela de login leva a uma URL sem página (ou redirect genérico).
  - **Página:** Criar algo como `ForgotPassword.tsx`: campo de e-mail, botão “Enviar link”, chamada a `authAPI.forgotPassword(email)` e mensagem de sucesso/erro (sem revelar se o e-mail existe).
- **Backend**
  - **POST /api/auth/forgot-password** hoje só devolve mensagem fixa; não:
    - Gera token de reset (ex.: JWT com short TTL ou token em tabela).
    - Envia e-mail com link de reset (dependência: serviço de e-mail, ex. SendGrid, SMTP).
  - **Página/rota de reset:** Ex.: `GET /reset-password?token=...` (página no frontend que envia token + nova senha para o backend).
  - **Endpoint:** Ex. `POST /api/auth/reset-password` com `{ token, new_password }` para validar token e atualizar senha no banco.

Resumo: para “Esqueci a senha” funcionar de verdade, falta: rota + tela “Esqueci a senha”, envio de e-mail no backend, geração/validação de token de reset e tela + endpoint de “nova senha”.

### 3.2 Lembrar-me

- O checkbox existe, mas o valor **não é usado** em lugar nenhum (nem no front nem no back).
- Para “lembrar-me” de fato, uma opção é: quando marcado, usar `refresh_token` com TTL maior e renovar sessão em background; ou persistir em `localStorage` com expiração longa (já é o que acontece hoje para token). Pode-se apenas documentar o comportamento atual ou implementar diferença explícita (ex.: sem “lembrar” = sessionStorage ou logout ao fechar aba).

### 3.3 Tratamento de erros e UX

- Mensagens de erro vêm do backend como string em `error`; está ok. Poderia padronizar códigos (ex. `invalid_credentials`, `email_not_found`) para i18n ou mensagens mais amigáveis.
- Não há tratamento específico para “conta vinculada ao Google” (backend já retorna 400 com mensagem); pode-se exibir esse caso com destaque na UI.
- Em 401 (token inválido/expirado), o interceptor redireciona para `/login`; pode-se opcionalmente mostrar um toast “Sessão expirada”.

### 3.4 OAuth Microsoft / Apple

- Backend retorna 501 para `/auth/microsoft/login` e `/auth/apple/login`.
- Na tela de login **não há botões** para Microsoft/Apple; só Google. Se forem adicionados no futuro, será preciso implementar os fluxos no backend e configurar client_id/secret.

### 3.5 Variáveis de ambiente e CORS

- **Frontend:** `VITE_API_URL` (ou `REACT_APP_BACKEND_URL`) deve apontar para o backend (ex.: `http://localhost:8001` em dev).
- **Backend:** `CORS_ORIGINS` deve incluir a origem do frontend (ex.: `http://localhost:5173`). Com `*` o app usa fallback para localhost.
- **Google OAuth:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, e no Google Cloud Console o redirect URI do callback (ex.: `https://api.alcahub.com.br/api/auth/google/callback` ou equivalente em dev).

---

## 4. Checklist rápido “o que falta para a tela de login funcionar”

- [x] Tela de login renderiza e envia email/senha.
- [x] Backend valida e retorna token e user.
- [x] Token e user armazenados; redirecionamento para dashboard.
- [x] Login com Google (se OAuth configurado).
- [ ] **Rota e página “Esqueci a senha”** (frontend).
- [ ] **Backend: gerar token de reset e enviar e-mail** em forgot-password.
- [ ] **Backend: endpoint + fluxo de “definir nova senha”** (reset-password).
- [ ] (Opcional) Usar “Lembrar-me” para diferenciar persistência de sessão.
- [ ] (Opcional) Mensagens/i18n e toast de “sessão expirada”.

---

## 5. Arquivos principais

| Papel | Arquivo |
|-------|--------|
| Tela de login | `frontend/src/components/auth/Login.tsx` |
| Rotas e proteção | `frontend/src/App.tsx` |
| Contexto de auth | `frontend/src/contexts/AuthContext.tsx` |
| Chamadas API (auth) | `frontend/src/utils/api.ts` (`authAPI`, `oauthAPI`) |
| Backend login/register/OAuth | `backend/routes/auth.py` |
| Config app (CORS, OAuth) | `backend/app.py` |

Com esse contexto, você sabe exatamente o estado atual da tela de login e o que falta para ela “funcionar” de ponta a ponta (em especial o fluxo de esqueci a senha e o uso opcional de “Lembrar-me”).
