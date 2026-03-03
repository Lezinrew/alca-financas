## Recipe: commit-conventional

**Goal:** Criar mensagens de commit curtas e padronizadas (estilo Conventional Commits simplificado).  

### Allowed prefixes

- `feat:` — nova funcionalidade
- `fix:` — correção de bug
- `docs:` — documentação
- `chore:` — manutenção, tooling, CI/CD
- `refactor:` — refatoração sem mudança de comportamento
- `test:` — testes e cobertura

### Steps

1. **Veja o diff atual:**
   ```bash
   git status
   git diff
   ```

2. **Adicione apenas o que faz sentido em um commit:**
   ```bash
   git add <arquivos-relacionados>
   ```

3. **Escreva a mensagem:**
   ```bash
   git commit -m "fix: corrige cálculo de limite do cartão"
   ```

4. **Commits com descrição longa (opcional):**
   ```bash
   git commit
   # linha 1: feat: adiciona tela de orçamento
   # linha 2: (em branco)
   # linhas 3+: explicação curta do porquê da mudança
   ```

### Tips

- Fale **o porquê**, não apenas o que mudou.
- Um commit deve idealmente tratar de um pequeno conjunto coeso de mudanças.

