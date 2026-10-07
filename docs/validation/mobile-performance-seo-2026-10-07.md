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

HTTP público após publicação: entrada, robots, release, duas imagens, CSS Bootstrap, fonte de ícones e health retornaram 200 com tipos corretos; robots é `text/plain`. Sessão existente continuou válida: contas a pagar, transações e dashboard carregaram sem alteração observada nos dados. Tela de importação foi aberta sem enviar arquivo; execução de importação e novo login com credenciais reais não foram realizados.

Primeira coleta: [PageSpeed 10:16 BRT](https://pagespeed.web.dev/analysis/https-alcahub-cloud/cihzw3u2fi?form_factor=mobile), Lighthouse 13.5.0/Moto G Power/4G lenta. Desempenho 89, acessibilidade 100, boas práticas 96, SEO 100; FCP 2,4 s, LCP 2,7 s, TBT 140 ms, CLS 0. A coleta revelou uma divergência nas dimensões declaradas da imagem oculta do painel desktop. Dimensões foram ajustadas para 240 × 157, iguais ao WebP base, e `sizes` mobile para os 96 pixels efetivamente usados. A revisão final 2b434ec foi publicada após esse ajuste. Essa medição intermediária não compõe a mediana final.

A API PageSpeed retornou HTTP 429; as três medições finais pela interface web concluíram. CSS/JS não usado permanece como oportunidade mensurada.
## Resultado final publicado — 2b434ec

Build de produção: sucesso (36,85 s). Nove verificações do CI aprovadas no commit de código. Após o ajuste final, TypeScript e os cinco testes de login passaram novamente. A suíte completa anterior teve 281 testes aprovados.

Três coletas mobile, mesmo perfil Lighthouse 13.5.0/Moto G Power/4G lenta:

| Coleta (BRT) | Desempenho | Acessibilidade | Boas práticas | SEO | FCP (s) | LCP (s) | TBT (ms) | CLS | SI (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [10:23](https://pagespeed.web.dev/analysis/https-alcahub-cloud/8kujm2wuiz?form_factor=mobile) | 91 | 100 | 100 | 100 | 2,450 | 2,600 | 0 | 0 | 4,516 |
| [10:25](https://pagespeed.web.dev/analysis/https-alcahub-cloud/nn8xd3cdu1?form_factor=mobile) | 90 | 100 | 100 | 100 | 2,464 | 2,614 | 32 | 0 | 4,709 |
| [10:27](https://pagespeed.web.dev/analysis/https-alcahub-cloud/d8kvr73x53?form_factor=mobile) | 91 | 100 | 100 | 100 | 2,422 | 2,572 | 0 | 0 | 4,618 |
| Mediana | **91** | **100** | **100** | **100** | **2,450** | **2,600** | **0** | **0** | **4,618** |

Referência original: desempenho 67, acessibilidade 98, boas práticas 100, SEO 83 e LCP 10,575 s, no relatório fornecido pelo titular. Metas de desempenho e SEO atingidas. **Meta de LCP ≤ 2,5 s não atingida**; mediana 2,6 s. Restam aproximadamente 300 ms de bloqueio de renderização, 59 KiB de CSS e 49 KiB de JS não usados segundo a auditoria. Uma coleta teve erro em auditoria de latência de rede; isso não foi interpretado como medição dessa latência. Sem dados de campo, os resultados são de laboratório e não garantem a mesma nota em toda sessão ou acessibilidade integral do aplicativo.

Integração no main pendente no [PR #5](https://github.com/Lezinrew/alca-financas/pull/5). A publicação isolou frontend para evitar recriar backend fora deste escopo. Um deploy futuro do main anterior ao merge pode sobrescrever esta entrega.

Rollback disponível no backup original acima: extrair em diretório separado, restaurar artefato frontend e Nginx salvos, validar Compose/Nginx e recriar somente frontend, verificando HTTP e sessão. A extração e comparação foram executadas; uma reversão real em produção não foi executada.

Evidência visual pública salva localmente em `C:/Users/lezin/.codex/artifacts/mobile-seo-2026-10-07/pagespeed-final.jpg`, fora do Git. Relatório não inclui credenciais, extratos ou valores financeiros pessoais. Não foi realizado novo login real, importação financeira ou medição de todas as rotas autenticadas.


## Continuação — integração e publicação do main

PR #5 integrado em 07/10/2026, merge 8061f7c. As nove verificações do PR e o CI do main passaram. O commit publicado tem árvore idêntica à revisão 939c3aa validada no PR. Build real no servidor: 36,53 s; publicação pelo novo script com Nginx/Compose validados, HTTP 200, sessão existente conferida e ID do backend preservado. Backup: /apps/alca-backups/8061f7cb1657ab79b1efa5817f9ff03895561363-20261007T134658Z/frontend-before.tar.gz.

O risco de sobrescrever as correções por falta de integração do PR #5 foi resolvido. Preload mobile presente no HTML público. Novas coletas:

- [10:49](https://pagespeed.web.dev/analysis/https-alcahub-cloud/m1u6s97105?form_factor=mobile): NO_LCP; desempenho/LCP/TBT indisponíveis. Excluída da comparação.
- [10:50](https://pagespeed.web.dev/analysis/https-alcahub-cloud/u1u40d7x95?form_factor=mobile): desempenho 89, SEO/acessibilidade/boas práticas 100, FCP 2,422 s, LCP 2,722 s, TBT 0 ms, CLS 0, SI 5,111 s.
- [Coleta seguinte](https://pagespeed.web.dev/analysis/https-alcahub-cloud/16m2iuhybj?form_factor=mobile): NO_LCP; excluída da comparação. Não existe mediana válida de três coletas desta revisão, nem evidência de ganho do preload isolado.

Auditoria npm de instalação apontou 34 alertas incluindo ferramentas de desenvolvimento. Auditoria --omit=dev do lockfile vigente: sete alertas (seis altos, um moderado), nenhum crítico. Lockfile não foi alterado nesta entrega; alertas requerem análise específica de aplicabilidade/atualização. A nota de boas práticas do Lighthouse não substitui essa análise.

Próxima hipótese limitada: remover a animação de entrada do login apenas até 640 px. A animação existente parte de opacity 0, dura 600 ms e inclui delays de 50/150/280 ms. A mudança não altera login ou layout; seu ganho deve ser medido após publicação, sem inferência de resultado.
