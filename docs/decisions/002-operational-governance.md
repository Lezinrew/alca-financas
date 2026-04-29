# ADR 002 — Governança operacional e documentação

**Status:** aceite  
**Aplica a:** colaboradores humanos e agentes (Cursor, CLI, automações).

## Princípios do projeto

1. **Mínimo necessário, mas verdadeiro** — documentação alinhada ao código e ao que está em `supabase/migrations/`.  
2. **Sem surpresas em produção** — alterações de schema passam por migration, revisão e aplicação explícita no Supabase.  
3. **Segurança por defeito** — nunca logar ou commitar segredos; `service_role` só no backend.  
4. **Recuperabilidade** — alguém que abre o repo deve encontrar: `README.md`, `system-design.md`, `docs/runbooks/runbook.md` e `docs/agents/01-execution-agent.md`.  
5. **Pequena superfície de mudança** — evitar refactors largos sem necessidade; respeitar `AGENTS.md` / red lines.

## Regra de atualização do runbook

- O ficheiro **`docs/runbooks/runbook.md`** é a **fonte única** para “estado atual”, “pendências” e “próximos passos” operacionais.  
- **Obrigatório atualizar** após: deploy relevante, conclusão de tarefa P0/P1 que mude premissas, alteração de auth/JWT, ou aplicação em massa de migrations.  
- Incluir **data** e um **evento** curto na secção 3 (última execução relevante), não apenas commits genéricos.

## Padrão de execução em 8 passos

1. **Ler** `README.md`, `system-design.md` e o **runbook** (secções 1–4).  
2. **Confirmar** branch e `git status`; identificar ficheiros tocados.  
3. **Carregar** `.env` a partir de `.env.example` onde faltar variáveis; **não** adicionar secrets ao git.  
4. **Reproduzir** o problema ou objetivo (local ou CI) de forma mínima.  
5. **Implementar** a mudança mais pequena que satisfaça o requisito.  
6. **Validar** (testes, lint, ou caminho manual documentado) conforme a área.  
7. **Atualizar documentação** se houver: schema → migration + nota no runbook; arquitetura → `system-design.md`.  
8. **Registar** no runbook o que mudou no ambiente ou nas pendências (secções 4–5).

## Obrigatoriedade de documentação em mudanças estruturais

| Tipo de mudança | Obrigatório |
|----------------|-------------|
| Novas tabelas, colunas, RLS, funções | Migration em `supabase/migrations/` + apontar no runbook se afetar deploy |
| Novo serviço externo obrigatório | `system-design.md` e `docs/ENVIRONMENTS.md` (ou guia linkado) |
| Alteração de fluxo auth/JWT | Runbook + guia de env se novas variáveis |
| Nginx/Docker/produção | `infra/README.md` e/ou `docs/DEPLOY*.md` conforme o caso |

Mudanças puramente cosméticas em UI **não** exigem ADR; mudanças que alterem contrato de API ou de dados **exigem** pelo menos nota no runbook e, se for decisão de produto, ADR em `docs/decisions/`.
