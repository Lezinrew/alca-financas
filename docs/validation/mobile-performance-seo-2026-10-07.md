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

Primeira publicação executada: `9b11103`, com build separado no servidor e variáveis públicas existentes usadas sem alteração/exposição de `.env`. Backend, banco, flags, regras financeiras e alterações locais de outras frentes não fazem parte desta mudança. A lista expansível de contas continua em entrega independente, sem alegação de publicação.

Backup: `/apps/alca-backups/mobile-seo-9b11103/frontend-before.tar.gz` (artefato, Nginx e Compose; sem `.env`). Extração em diretório separado e comparação de `index.html`/Nginx executadas com sucesso. Nova configuração validada em container Nginx isolado na rede existente; Compose validado antes da troca. Apenas frontend foi recriado; ID do backend permaneceu igual. Assets anteriores conservados para abas já abertas.

HTTP público após publicação: entrada, robots, release, duas imagens, CSS Bootstrap, fonte de ícones e health retornaram 200 com tipos corretos; robots é `text/plain`. Sessão existente continuou válida: contas a pagar manteve os quatro registros e R$ 2.346,67 da competência outubro, transações e dashboard carregaram. Tela de importação foi aberta sem enviar arquivo; execução de importação e novo login com credenciais reais não foram realizados.

Primeira coleta: [PageSpeed 10:16 BRT](https://pagespeed.web.dev/analysis/https-alcahub-cloud/cihzw3u2fi?form_factor=mobile), Lighthouse 13.5.0/Moto G Power/4G lenta. Desempenho 89, acessibilidade 100, boas práticas 96, SEO 100; FCP 2,4 s, LCP 2,7 s, TBT 140 ms, CLS 0. A coleta revelou uma divergência nas dimensões declaradas da imagem oculta do painel desktop. Dimensões foram ajustadas para 240 × 157, iguais ao WebP base, e `sizes` mobile para os 96 pixels efetivamente usados. Nova coleta pendente após esse ajuste. Essa medição intermediária não compõe a mediana final.

A API PageSpeed retornou HTTP 429; a interface web conseguiu medir. As metas de desempenho/LCP ainda não foram comprovadas. CSS/JS não usado permanece como oportunidade mensurada; nenhuma conclusão antecipada de 90 ou LCP ≤ 2,5 s.
