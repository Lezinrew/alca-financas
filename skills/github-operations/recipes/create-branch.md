## Recipe: create-branch

**Goal:** Criar uma nova branch de trabalho seguindo convenções simples e previsíveis.

### Steps

1. **Atualize a branch principal local:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Escolha o tipo de branch:**
   - `feat/` — nova funcionalidade
   - `fix/` — correção de bug
   - `chore/` — manutenção e tarefas internas
   - `docs/` — documentação

3. **Crie a branch:**
   ```bash
   git checkout -b <tipo>/<slug-curto>
   # exemplo:
   # git checkout -b feat/budget-screen
   ```

4. **Verifique o estado:**
   ```bash
   git status
   ```

5. **Suba a branch para o remoto quando tiver commits:**
   ```bash
   git push -u origin <tipo>/<slug-curto>
   ```

### Notes

- Mantenha o nome da branch curto e descritivo.
- Evite caracteres especiais e espaços.

