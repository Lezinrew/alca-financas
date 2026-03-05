# Teste: Criação de categoria "Doações" e diagnóstico tenant_id

## Por que o CI não rodou no push?

O workflow de CI só dispara quando **todas** as condições são verdadeiras:

1. **Branch:** o push foi em `main` ou `develop` (não em outra branch).
2. **Paths:** o commit alterou pelo menos um arquivo em:
   - `backend/**`
   - `frontend/**`
   - `scripts/**`
   - `docs/**`
   - `skills/**`
   - `.github/workflows/**`
   - `Makefile`

Se o push foi só em `main` mas o commit não mexeu em nenhum desses caminhos (por exemplo só em `supabase/` ou arquivos na raiz), o CI **não roda**.

**Como rodar o CI manualmente:**

1. Abra o repositório no GitHub.
2. Vá em **Actions**.
3. No menu à esquerda, clique em **CI/CD Pipeline - Supabase**.
4. Clique em **Run workflow** (botão à direita), escolha o branch (ex.: `main`) e **Run workflow**.

Assim o CI roda mesmo que o último push não tenha batido nos paths. Depois que o CI terminar com sucesso, o **Deploy to Production** pode ser disparado (conforme configurado no workflow de deploy).

---

## Produção tem essas mudanças?

**Não.** O commit com as correções (`feat(categories): add description field and improve tenant resolution`) está **apenas local** (você está `ahead 1` do `origin/main`). O servidor de produção é atualizado quando:

1. Você faz **push** para `main`: `git push origin main`
2. O **CI** roda e passa (workflow "CI/CD Pipeline - Supabase")
3. O **Deploy to Production** roda (automático após CI em `main`)

Enquanto não fizer push e o deploy não rodar, **produção continua com o código antigo**.

Para confirmar em produção depois do deploy: crie uma categoria no app em produção e veja se o campo "Descrição" aparece no formulário e se a criação funciona (ou se aparece a mensagem clara "Workspace não identificado..." nos logs/UI).

---

## Como testar localmente

### 1. Subir o backend com logs visíveis

No terminal, na raiz do projeto:

```bash
cd backend
python -m venv .venv  # só se ainda não tiver
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
export FLASK_APP=app.py
export FLASK_DEBUG=1
python app.py
```

Ou, se usar variáveis de ambiente do Supabase:

```bash
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="sua-service-role-key"
python app.py
```

Deixe esse terminal aberto para ver os logs.

### 2. Subir o frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Acesse o endereço que o Vite mostrar (ex.: http://localhost:5173).

### 3. Fluxo do teste

1. Faça **login** no app (para ter `user_id` e token).
2. Vá em **Categorias** e clique para **Nova categoria**.
3. Preencha:
   - **Nome:** Doações
   - **Tipo:** Receita (income)
   - **Descrição (opcional):** Ex.: "Doações recebidas, contribuições, etc."
4. Clique em **Salvar**.

### 4. O que observar

**No navegador**

- Se der certo: categoria "Doações" aparece na lista.
- Se der erro de tenant: mensagem tipo **"Workspace não identificado. Por favor, recarregue a página ou faça login novamente."** (vinda do `category_service`).

**No terminal do backend**

- **Se o tenant for criado:**  
  - `ensure_default_tenant: Criando tenant para usuário ...`  
  - `ensure_default_tenant: Tenant ... criado, adicionando membership ...`  
  - `ensure_default_tenant: Membership criado com sucesso ...`
- **Se o usuário já tiver tenant:**  
  - `ensure_default_tenant: Usuário ... já tem tenant ...`
- **Se der erro ao criar tenant (ex.: RLS/permissão no Supabase):**  
  - `ensure_default_tenant: Erro ao criar tenant ...` + stack trace.
- **Se o tenant não for resolvido (ex.: `ensure_default_tenant` retorna `None`):**  
  - A rota retorna 403 e o serviço pode retornar a mensagem "Workspace não identificado...".

### 5. Resumo do diagnóstico

| Onde aparece o problema | Provável causa |
|-------------------------|----------------|
| Logs em `ensure_default_tenant` (erro ao criar tenant) | Permissão/RLS no Supabase (tabelas `tenants` / `tenant_members`) ou FK (ex.: `user_id` não existe em `users`) |
| Mensagem "Workspace não identificado" na tela | `tenant_id` ficou `None` (tenant não resolvido ou criação falhou) |
| Erro 403 com `code: "tenant_required"` | Decorator `require_tenant` não conseguiu tenant (incluindo falha em `ensure_default_tenant`) |

Depois do teste, se ainda falhar, envie os trechos relevantes dos **logs do backend** (em especial as linhas com `ensure_default_tenant` e o traceback, se houver) para analisar a causa.

---

## 404 no console ao abrir o Dashboard ("dashboard:1 Failed to load resource")

Esse 404 costuma ser **uma requisição** que está falhando (não necessariamente a rota `/dashboard` do front). Para descobrir a causa:

1. Abra **DevTools** (F12) → aba **Rede** (Network).
2. Marque **Fetch/XHR** (e, se quiser, **Doc**).
3. Faça login e vá para o dashboard (ou recarregue na página do dashboard).
4. Procure a requisição em **vermelho** com status **404** e anote a **URL completa** que falhou.

Interpretação:

| URL que retornou 404 | Causa provável | O que fazer |
|----------------------|----------------|-------------|
| `.../api/dashboard-advanced` ou `.../api/accounts` | Backend em produção sem essa rota ou deploy desatualizado | Conferir se o backend em produção está com as rotas `/api/dashboard-advanced` e `/api/accounts` (deploy, variáveis, reinício do serviço). |
| `.../dashboard` (sem `/api`) no host da API | Front chamando a API sem o prefixo `/api` | Garantir que a URL base da API termine em `/api` (ex.: `VITE_API_URL=https://api.alcahub.cloud` → o código já usa `.../api`; não use `.../api/api`). |
| URL do tipo `.../assets/...` ou `.../Dashboard-....js` | Chunk/asset do front não encontrado (SPA ou base path) | Quem serve o front (Nginx, Vercel, etc.) deve devolver `index.html` para rotas do app (fallback SPA). Se o app estiver em subpasta, configurar `base` no Vite e o servidor de acordo. |

**Nginx (produção):** o `nginx.conf` do projeto já tem `try_files $uri $uri/ /index.html;` em `location /`, então `/dashboard` deve devolver o `index.html`. Se em produção você usar outro servidor (outro Nginx, Caddy, Vercel, etc.), configure o **fallback SPA** (sempre servir `index.html` para rotas do app).

---

## Erro "null value in column tenant_id" ao salvar categoria

Se ao clicar em **Salvar** na nova categoria aparece **500** e a mensagem de constraint `tenant_id` null na tabela `categories`, significa que o backend está criando a categoria **sem** `tenant_id`.

**Causa mais comum:** o servidor em produção (ex.: `anl.alcahub.cloud`) está rodando uma **versão antiga** do backend, sem o fluxo de tenant (`@require_tenant`, `ensure_default_tenant` e a checagem de `tenant_id` na rota).

**O que fazer:**

1. **Fazer deploy da versão atual**
   - Garantir que o código com `require_tenant` na rota de categorias, `ensure_default_tenant` no tenant context e a checagem explícita de `tenant_id` no POST de categorias está no repositório e é o que sobe em produção.
   - Depois do deploy, reiniciar o backend em produção.

2. **Se após o deploy o erro continuar (ou aparecer 403 "Workspace não identificado")**
   - O backend tenta criar um workspace padrão para o usuário em `tenants` e `tenant_members`.
   - O backend precisa usar a **service role key** do Supabase (não a anon key) para não ser bloqueado por RLS.
   - O usuário precisa existir em **`public.users`**: a tabela `tenant_members` tem FK `user_id REFERENCES public.users(id)`. Se você usa só Supabase Auth, é preciso um trigger (ou processo) que crie/atualize a linha em `public.users` quando o usuário se registra ou faz login.

3. **Verificação na rota (já no código)**
   - Na rota POST `/api/categories` há uma checagem: se `tenant_id` estiver vazio, a API responde **403** com a mensagem *"Workspace não identificado. Recarregue a página ou faça login novamente."* em vez de 500. Assim você distingue:
     - **403** = backend novo rodando, mas não conseguiu resolver/criar tenant (ver item 2).
     - **500** com constraint `tenant_id` = backend antigo ainda em produção (ver item 1).
