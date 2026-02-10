# Entrega: Upgrade da Tela de Login – Alça Finanças

## Arquivos criados

| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/components/ui/gradient-button.tsx` | Botão com variantes default e gradient (CVA + Radix Slot). |
| `frontend/src/utils/tokenStorage.ts` | Helper: localStorage vs sessionStorage conforme "Lembrar-me", get/set/clear auth. |
| `frontend/src/components/auth/ForgotPassword.tsx` | Página "Esqueci a senha": formulário e-mail, mensagem genérica, loading. |
| `frontend/src/components/auth/ResetPassword.tsx` | Página "Nova senha": token na URL, formulário senha + confirmação, GradientButton. |
| `backend/services/email_service.py` | Envio de e-mail de reset; em dev loga o link no console. |

## Arquivos modificados

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/components/auth/Login.tsx` | Redesign premium: card glassmorphism, fundo com gradiente + noise, inputs com ícones (Mail, Lock), erro elegante, GradientButton como CTA, "Lembrar-me" enviado ao login, Google ativo / Microsoft e Apple "Em breve" (desabilitados + title). |
| `frontend/src/contexts/AuthContext.tsx` | login(credentials, rememberMe?), register(..., rememberMe?); uso de tokenStorage (setAuthTokens, getAuthToken, getUserData, clearAuthStorage); checkAuth e logout usando tokenStorage. |
| `frontend/src/utils/api.ts` | Request interceptor usa getAuthToken(); em 401: clearAuthStorage(), toast "Sua sessão expirou. Entre novamente.", redirect /login; authAPI.resetPassword(token, newPassword). |
| `frontend/src/main.tsx` | Toaster (react-hot-toast) adicionado. |
| `frontend/src/App.tsx` | Rotas /forgot-password e /reset-password (PublicRoute), imports ForgotPassword e ResetPassword. |
| `frontend/src/index.css` | Estilos do Gradient Button (@property, radial-gradient, hover); .bg-login-page, .card-login, .input-with-icon, .input-error. |
| `backend/utils/auth_utils.py` | generate_reset_token(user_id), decode_reset_token(token); removido "return decorated" duplicado. |
| `backend/routes/auth.py` | forgot_password: gera token, monta reset_url, send_reset_link (e-mail ou log dev); POST /auth/reset-password: valida token, atualiza senha no usuário. |

## Dependência adicionada

- `react-hot-toast` (já existentes: `@radix-ui/react-slot`, `class-variance-authority`).

---

## Checklist QA

- [ ] **Login e-mail/senha** – Preencher e enviar; redireciona para /dashboard; token e user persistidos.
- [ ] **Login com erro** – Credenciais inválidas; mensagem de erro exibida (estilo âmbar, não “caixa vermelha crua”).
- [ ] **Login com Google** – Botão "Continuar com Google" redireciona para OAuth; após callback, volta ao app e dashboard.
- [ ] **Microsoft / Apple** – Botões desabilitados; atributo title="Em breve".
- [ ] **Lembrar-me** – Marcado: auth em localStorage (persiste ao fechar navegador). Desmarcado: sessionStorage (limpa ao fechar aba).
- [ ] **Esqueci a senha** – Acessar /forgot-password; informar e-mail; enviar; mensagem genérica; em dev, link de reset no console do backend.
- [ ] **Reset de senha** – Abrir link /reset-password?token=... (token do console); preencher nova senha e confirmação; sucesso e redirecionamento para login; login com nova senha funciona.
- [ ] **Sessão expirada** – Com token inválido/expirado, uma chamada 401 deve exibir toast "Sua sessão expirou. Entre novamente.", limpar storage e redirecionar para /login.
- [ ] **Links** – "Esqueci a senha" → /forgot-password; "Cadastre-se" → /register; "Voltar ao login" nas telas de forgot/reset.
- [ ] **Build** – `npm run build` no frontend conclui sem erros.

---

## Notas

- **Gradient Button:** O padrão shadcn (CVA + Slot + cn) mantém consistência e reutilização no design system.
- **tokenStorage:** Centraliza onde os tokens são gravados (local vs session) sem reescrever todo o AuthContext.
- **Backend e-mail:** Sem SMTP configurado, o link de reset é impresso no console do servidor (modo dev).
