# ADR 0008 — Migração do FinanceOS e OFX como fonte única do realizado

**Status:** aceite (implementado)
**Contexto:** Antes do Alça Finanças, o controlo financeiro pessoal do fundador vivia no `FinanceOS` — uma pasta local (`C:\Users\lezin\OneDrive\Documentos\FinanceOS`) com uma planilha Excel (`TabelaTransacoes`) e extratos bancários em OFX. Este ADR documenta a migração desses dados para o Supabase e a decisão consequente sobre qual fonte é autoritativa para os cálculos financeiros. Não existia registo formal desta decisão além de mensagens de commit; este documento consolida o que já estava implementado.

## Decisão

1. **Fase 1 — Migração pontual do Excel (2026-07-26).** Script `scripts/migrate_financeos_data.py` lê `TabelaTransacoes` via `openpyxl`, mapeia categoria/status/tipo e deduplica via `compute_dedup_key` (reaproveitado de `backend/services/import_service.py`) contra o histórico já existente no tenant. Migration `20260726000004_transactions_legacy_id_source_file.sql` adiciona `legacy_id` (ID original da planilha) e `source_file` para rastreabilidade pós-migração.

2. **Fase 2 — OFX como SSOT ("single source of truth") do realizado (2026-07-28).** Apenas transações com `source_file` terminado em `.ofx` entram em saldo, relatórios, contas pagas e respostas de IA. CSV, PDF, entradas manuais e registos migrados do Excel (`legacy:*`) ficam fora dos cálculos operacionais, mas são preservados no banco para consulta e rollback. Implementado em:
   - `backend/repositories/transaction_repository_supabase.py` — `CANONICAL_SOURCE_PATTERN = "%.ofx"`, aplicado via `.ilike('source_file', ...)` em todas as queries de saldo/relatório/listagem.
   - `backend/routes/transactions.py` — grava `source_file` = nome do ficheiro importado.

3. **Sincronização contínua.** `scripts/sync_financeos_ofx_ssot.py` sincroniza novos extratos OFX do FinanceOS para o modelo multi-tenant do Alça. É uma ferramenta manual — não faz parte de nenhum pipeline automatizado — com **dry-run por padrão**; exige `--apply` explícito para gravar.

## Resultado da execução

- **Fase 1:** 39/40 linhas válidas migradas, 0 duplicatas contra 126 transações já existentes, 9 categorias novas criadas. Backup pré-migração guardado localmente (fora do repositório).
- **Fase 2:** 157 receitas/despesas canónicas sincronizadas; 16 transferências internas excluídas do fluxo operacional (não são receita nem despesa).

## Consequências

- **Positivo:** fonte de verdade única e auditável para os números financeiros exibidos ao utilizador; dados legados preservados (sem perda de histórico), mas isolados dos totais atuais.
- **Negativo / risco:** `sync_financeos_ofx_ssot.py` tem como valor por omissão um caminho local do Windows (`C:\Users\lezin\OneDrive\Documentos\FinanceOS`) — só corre manualmente, nessa máquina, sem automação nem alerta para extratos pendentes de sincronizar. Se o fundador trocar de máquina ou perder esse diretório, o processo de sync precisa de ser readaptado.
- **Documentação:** `docs/runbooks/runbook.md` (secção "Contexto válido") regista a regra de fonte do realizado; `TODO.md` tem uma nota datada de 2026-07-28, mas o cabeçalho do ficheiro não foi atualizado desde 2026-04-17 — risco de leitura desalinhada para quem só olhar o topo do documento.

## Referências

- Commits: `41eebc55` (Fase 1 — migração do Excel), `8a49f085` (Fase 2 — OFX como SSOT)
- `docs/runbooks/runbook.md` (secção "Contexto válido")
- `TODO.md` (secção "Concluído recentemente")
