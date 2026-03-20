# Prompt para avaliação da estrutura do projeto (Claude CLI)

Use este prompt com o Claude CLI para avaliar a estrutura do repositório e gerar um TODO de melhorias.

**Requisito:** Claude CLI no PATH. Se instalou e o comando não é encontrado:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Uso:**
```bash
cd /caminho/para/alca-financas
claude "$(cat PROMPT-AVALIACAO-ESTRUTURA.md)"
```

Se o Claude CLI retornar "Credit balance too low", você pode rodar a avaliação no Cursor: o resultado já foi gerado em **`docs/TODO-MELHORIAS-ESTRUTURA.md`**.

Ou abra o arquivo, copie o conteúdo da seção "Prompt" abaixo e cole no chat do Claude.

---

## Prompt

Você é um engenheiro de software experiente. Analise a estrutura do repositório **alca-financas** (aplicação full stack de finanças pessoais) e produza um **TODO estruturado de possíveis melhorias**.

### Contexto do projeto (resumo)
- **Backend:** Flask (Python), rotas em `backend/routes/`, repositórios Supabase em `backend/repositories/`, serviços em `backend/services/`, banco apenas Supabase (PostgreSQL).
- **Frontend:** React + TypeScript + Vite, componentes em `frontend/src/components/`, contextos (Auth, Theme), API em `frontend/src/utils/api.ts`.
- **Mobile:** pasta `mobile/` (React Native/Expo).
- **Scripts:** `alca_start_mac.sh` / `alca_stop_mac.sh`, scripts de deploy e seed em `scripts/`.
- **Docs:** `docs/`, vários `.md` de features e fixes na raiz.

### O que fazer
1. **Percorra a estrutura** (raiz, backend, frontend, mobile, scripts, docs) e identifique:
   - Organização de pastas e nomenclatura
   - Duplicação ou código morto (ex.: referências a MongoDB após migração para Supabase)
   - Consistência entre backend e frontend (rotas, tipos, erros)
   - Segurança (env, secrets, CORS, auth)
   - Testes (cobertura, tipos de teste)
   - Performance e boas práticas (lazy load, bundle, queries)
   - Documentação (README, .env.example, comentários)
   - DevOps e deploy (CI, scripts, Docker)
   - Acessibilidade e i18n (já há i18n em `frontend/src/i18n/`)
   - Dívida técnica (arquivos .bak, scripts obsoletos, dependências desatualizadas)

2. **Gere um TODO** em Markdown com:
   - **Título** por categoria (ex.: Arquitetura, Segurança, Testes, Performance, Documentação, DevOps, Limpeza).
   - Itens **priorizados** (ex.: [P0] crítico, [P1] importante, [P2] desejável).
   - Cada item com: **descrição curta**, **onde** (arquivo/pasta ou área) e **sugestão de ação** em uma linha.
   - Ao final, um **resumo** com 5–10 ações de maior impacto sugeridas primeiro.

3. **Seja objetivo e acionável:** evite genéricos; cite arquivos ou padrões concretos quando possível.

Formato de saída esperado: um único documento Markdown com o TODO de melhorias e o resumo final.
