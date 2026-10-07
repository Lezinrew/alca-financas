# RFC 0004 — Correções de desempenho mobile e SEO público

Data: 07/10/2026  
Status: aprovada pelo titular em 07/10/2026; implementação em validação  
Responsável pela aprovação: titular do Alça Finanças  
Decisões: [ADR 0009](../decisions/0009-mobile-performance-and-public-seo.md)

## Objetivo e escopo

Reduzir o custo inicial da entrada pública e corrigir defeitos de SEO e acessibilidade do PageSpeed indicado na ADR, preservando o app financeiro. O escopo inicial inclui imagem da marca, semântica do login, metadescrição e entrega correta de robots. CSS/JS será otimizado somente mediante evidência de uso e testes. A lista expansível mobile é uma entrega separada já iniciada; seu código local ainda precisa de validação e não deve ser declarado publicado.

## Plano de execução

### 1. Preparar uma base isolada

- Após aprovação, conferir main remoto e configuração de deploy; criar branch `codex/mobile-performance-seo` em checkout isolado.
- Preservar integralmente as alterações locais de marca, login, despesas, documentação e outras frentes; não fazer stash, reset ou incluir arquivos alheios no commit.
- Comparar login em produção, main e alterações locais antes de escolher a base. Não substituir o trabalho de marca por uma versão histórica.
- Registrar baseline do build, tamanho da imagem e resultado dos testes existentes. Conferir qual Nginx e Dockerfile servem a produção, sem ler/expor secrets.

### 2. Corrigir os quatro problemas principais

| Mudança | Arquivos candidatos | Validação |
| --- | --- | --- |
| Logo responsiva WebP, variantes para 1x/2x e tamanho desktop | `frontend/public/`, `Login.tsx`, `LoginVisualPanel.tsx` e outros consumidores encontrados | proporção/transparência, dimensões explícitas, rede sem PNG original no login mobile, nitidez em 2x |
| Marco principal | `frontend/src/components/auth/Login.tsx` | um `main`, teclado, labels e foco preservados |
| Metadescrição factual | `frontend/index.html` | HTML do build e página pública contêm descrição válida |
| Robots real | `frontend/public/robots.txt` e configuração Nginx realmente usada, se necessário | HTTP 200, tipo texto, corpo sem HTML; arquivo ausente não vira SPA |

Não alterar login, sessão, CSRF, APIs ou regras financeiras. Não adicionar dados pessoais à metadescrição ou robots. Usar nomes versionados nas novas imagens para evitar cache antigo. Conferir presença dos arquivos no `dist` e na imagem Docker.

### 3. Reduzir bloqueios de CSS/JS com escopo controlado

- Inventariar Bootstrap CSS, ícones e bundle JS externos, imports de gráficos e carregamento de rotas.
- Só aplicar carregamento sob demanda ou retirada de recurso quando consumidores e fallback estiverem conhecidos.
- Comparar o build antes/depois e testar login, dashboard, contas a pagar, transações e importação. Se houver risco ou ganho não demonstrável, registrar pendência em vez de retirar a biblioteca.
- Sem troca de framework, refatoração geral ou promessa de eliminar todo CSS não usado.

### 4. Validar e preparar revisão

- Na pasta `frontend`: `npx --no-install tsc --noEmit`, `npm run test:run` e `npm run build`; registrar números reais e falhas preexistentes.
- Testes focados para marco principal e fluxo de login; verificar robots e ativos no build. Não executar testes backend com `.env` real.
- Conferência visual local em 360, 390 e 768 pixels e desktop; login, mensagens de erro, teclado, expansão da lista em sua entrega própria e rotas SPA diretas.
- Validar configuração Nginx e Compose antes de qualquer publicação. Não subir Docker sem essa validação.
- Produzir diff revisável, capturas sem dados pessoais e inventário de arquivos alterados. Atualizar runbook com resultado observado, não com conclusão antecipada.

### 5. Publicar e medir, em etapa operacional própria

- Antes de mudar produção: backup do artefato/configuração vigente, identificação da versão para rollback e confirmação do mecanismo de restauração; nenhuma migration necessária.
- Commit/push somente no escopo autorizado na conversa, sem arquivos de outras frentes. Conferir autorização de publicação aplicável antes de deploy; aprovação deste plano não dispensa backup ou verificações.
- Após publicar: health, login real pelo titular quando exigir credenciais, navegação e recursos estáticos; sem criar/excluir dados financeiros para testar.
- Rodar três medições mobile comparáveis da entrada pública e registrar mediana, parâmetros e links. Diferenciar baseline antigo de nova coleta; não usar sessão autenticada ou dados financeiros em serviço externo.

## Critérios de aceite

- Logo entregue no mobile com orçamento de até 50 KiB, incluindo variantes solicitadas nessa navegação, sem mudança visual perceptível; confirmar medição efetiva.
- Metadescrição presente, robots válido e marco principal reconhecido; defeitos correspondentes deixam de aparecer na nova auditoria.
- TypeScript, build e testes relevantes passam, com números documentados; login e telas financeiras não regridem.
- Meta de desempenho: mediana mobile ≥ 90 e LCP ≤ 2,5 s no mesmo perfil de laboratório. São metas, não garantias. Se não forem atingidas, registrar os gargalos restantes e não declarar a meta concluída.
- SEO alvo ≥ 95 na entrada pública, sem liberar dados privados para rastreamento. Acessibilidade ≥ 98, CLS ≤ 0,1 e sem piora material de TBT.
- Nova versão e rollback identificados; evidências não contêm dados pessoais, tokens ou secrets.

## Riscos, reversão e fora de escopo

Riscos: cache de imagem antiga, perda de nitidez, regressão de estilos globais, divergência entre Nginx local e VPS e variação de rede no Lighthouse. Mitigar com nomes versionados, revisão visual, validação do servidor efetivo e medições repetidas.

Rollback: restaurar o artefato anterior e a configuração Nginx salva, validar servidor e health; reverter o commit isolado quando necessário. Sem tocar no banco ou em registros financeiros.

Fora de escopo: campanhas/marketing, indexação de áreas privadas, autenticação nova, migrations, IA/agentes, integrações de e-mail/WhatsApp e redesign integral.

## Aprovação e evidências

Plano aprovado pelo titular em 07/10/2026. A execução e seus limites serão registrados em `docs/validation/mobile-performance-seo-2026-10-07.md`; os resultados históricos de outros testes não valem como validação desta mudança.
