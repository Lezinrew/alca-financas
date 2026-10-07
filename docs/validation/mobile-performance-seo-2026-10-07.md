# Validação — desempenho mobile e SEO público

Data: 07/10/2026. Branch: `codex/mobile-performance-seo`.
Referências: ADR 0009 e RFC 0004, aprovadas pelo titular.

## Validação local executada

- Suíte frontend: **281 testes aprovados em 28 arquivos** (Vitest, dois workers).
- Após adequar `fetchpriority` ao React 18: **5 testes de login aprovados**.
- TypeScript: `npx --no-install tsc --noEmit`, saída 0.
- Build Vite: sucesso, com variáveis fictícias de prévia; este artefato local não é próprio para produção. A produção precisa de build separado com suas variáveis públicas existentes.
- Conferência pelo navegador em 360, 390, 768 e 1280 pixels: sem overflow horizontal, imagem carregada, um marco `main`. Formulário vazio exibe validação; Tab do e-mail chega à senha. Não foram usados dados ou credenciais reais nessa prévia.
- PNG original preservado: 1.552.619 bytes, 3320 × 2168 e transparência.
- WebP 240: 9.888 bytes; WebP 480: 22.668 bytes. Transparência preservada. Soma das duas variantes: 32.556 bytes, abaixo do orçamento de 50 KiB.
- Recursos Bootstrap 5.3.2 e Icons 1.11.2 servidos localmente com versões e licenças preservadas; bundle deferido. CSS não usado permanece como dívida, sem remoção insegura de estilos globais.
- Estado de produção antes da publicação: repositório `c3ac1f0`, frontend Nginx com volume `build/frontend` e configuração `nginx.conf`; Compose e Nginx existentes válidos.

## Limites e publicação

Publicação e nova medição ainda pendentes neste registro inicial. Backend, banco, flags, regras financeiras e alterações locais de outras frentes não fazem parte desta mudança. A lista expansível de contas continua em entrega independente, sem alegação de publicação.

Não há nova nota PageSpeed confirmada nesta etapa. A meta 90 de desempenho e 95 de SEO não é uma conclusão. Evidências visuais de produção e comparação serão acrescentadas após execução.
