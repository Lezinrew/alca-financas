## Recipe: rollback

**Goal:** Reverter rapidamente para uma versão anterior conhecida em caso de incidente.

### Pré-requisitos

- Releases versionadas via tags (`vX.Y.Z`).
- `scripts/prod/rollback.sh` configurado para aplicar a versão anterior.

### Steps (alta-nível)

1. **Identifique a última versão estável:**
   ```bash
   git tag --sort=-creatordate | head -n 5
   # escolha a última versão conhecida estável (ex.: v1.2.3)
   ```

2. **Acione rollback via script:**
   ```bash
   ./scripts/prod/rollback.sh v1.2.3
   ```

3. **Valide após rollback:**
   - Testar login.
   - Testar dashboard.
   - Testar operação crítica (ex.: criação de transação).

### Notes

- Se `rollback.sh` ainda não estiver implementado para trocar imagens/tags, adicione um TODO explícito no script com a estratégia planejada.
- Registre sempre o motivo do rollback em issue ou comentário na release.

