## Recipe: review-pr

**Goal:** Fazer review de PR com foco em riscos reais e baixo uso de tokens.

### Scope de leitura

Para revisão por agente de IA:
- `skills/README.md`
- `skills/SKILLS_REGISTRY.md`
- `skills/github-operations/skill.md`
- Apenas os arquivos modificados no PR (diff).

### Checklist de revisão

1. **Compilação e testes locais (ideal):**
   ```bash
   make lint
   make test
   make typecheck
   make build
   ```

2. **Revisão de código:**
   - O skill certo está sendo alterado? (veja `skills/SKILLS_REGISTRY.md`).
   - Há mudanças em contratos de API ou DB? Se sim, peça atualização de docs/skills.
   - Procure por possíveis quebras de compatibilidade (inputs/outputs).

3. **Segurança e dados:**
   - Nenhum secret, token ou senha em código ou docs.
   - Sem logs com PII sensível.

4. **Docs & testes:**
   - Se houve mudança de comportamento, peça:
     - Atualização de documentação relevante em `docs/` ou `skills/<skill>/`.
     - Testes cobrindo o caminho principal alterado.

5. **Conclusão:**
   - Aprove se:
     - Passa nos checks de CI.
     - Não introduz riscos óbvios.
   - Caso contrário, deixe comentários claros e objetivos.

