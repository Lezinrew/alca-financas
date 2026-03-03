## Recipe: release

**Goal:** Criar uma release versionada a partir de `main`, com changelog básico.

### Steps

1. **Garanta que `main` está saudável:**
   ```bash
   git checkout main
   git pull origin main
   make ci
   ```

2. **Escolha a versão (semver):**
   - `MAJOR` — breaking changes.
   - `MINOR` — novas features compatíveis.
   - `PATCH` — correções e ajustes.

3. **Crie e anote o tag:**
   ```bash
   VERSION=vX.Y.Z
   git tag -a "$VERSION" -m "Release $VERSION"
   git push origin "$VERSION"
   ```

4. **Deixe o changelog para o CI/automação:**
   - Workflow de release pode gerar changelog automático a partir de commits.
   - Se necessário, adicione um resumo em `CHANGELOG.md` ou comentário na release GitHub.

### Notes

- Nunca faça tag em branch que não seja `main`.
- Sempre rode os testes antes de criar o tag.

