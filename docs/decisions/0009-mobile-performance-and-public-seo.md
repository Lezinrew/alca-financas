# ADR 0009 — Desempenho mobile e SEO da entrada pública

Data: 07/10/2026  
Status: aceita pelo titular em 07/10/2026; implementação em validação  
Execução: [RFC 0004](../rfcs/0004-mobile-performance-and-public-seo.md)

## Contexto

O [PageSpeed mobile de 07/10/2026](https://pagespeed.web.dev/analysis/https-alcahub-cloud/nhktp19o5t?form_factor=mobile) mediu a entrada pública de `alcahub.cloud`: desempenho 67, acessibilidade 98, boas práticas 100 e SEO 83. LCP 10,6 s, FCP 2,7 s, TBT 0 ms e CLS 0. Não há dados de campo disponíveis; estes números são de laboratório, não da tela autenticada.

A logo PNG tem 1.552.619 bytes e 3320 × 2168 pixels, sendo exibida em 168 × 110. O relatório estima economia de 1.513 KiB em imagens e 610 ms em recursos que bloqueiam renderização. Identifica ausência de metadescrição e de marco principal; `robots.txt` responde com HTML (24 erros). O código local confirma referência ao PNG, ausência da metadescrição e CSS Bootstrap externo no HTML. A configuração efetivamente implantada ainda deve ser conferida.

## Decisões propostas

1. Priorizar a imagem de marca: gerar variantes pequenas em WebP, conservar transparência e proporção, usar nome versionado e dimensões explícitas. Manter o original para reversão. Não redesenhar a marca. A imagem principal não terá carregamento lazy.
2. Corrigir semântica com um único `main` visível na página de login e preservar formulários, navegação e autenticação.
3. Acrescentar metadescrição factual à entrada pública; não anunciar IA ativa ou capacidades não homologadas.
4. Servir `robots.txt` como texto, sem fallback da SPA. Permitir rastreamento da entrada pública e desaconselhar rastreamento de rotas privadas/API. Isso não é controle de acesso: sessões, JWT e RLS continuam obrigatórios. Não abrir rotas financeiras para obter nota de SEO. Não criar sitemap de rotas privadas.
5. Revisar CSS/JS em uma segunda etapa medida. Não retirar Bootstrap ou bibliotecas globais antes de identificar consumidores e validar os fluxos autenticados. Não remover dependências apenas para melhorar a pontuação.
6. Não implementar `llms.txt`, catálogo de agentes, novas integrações ou mudanças de CSP/HSTS nesta rodada: não são necessários para resolver os defeitos principais e exigem análise própria.

## Alternativas

- Apenas metadescrição e robots: resolve parte de SEO, mas deixa o principal custo mobile.
- Redesenho completo e remoção imediata de Bootstrap: risco alto de regressão em telas fora do login; rejeitado para esta rodada.
- Indexar todas as telas: inadequado para dados financeiros privados; rejeitado.

## Consequências e limites

Espera-se menor transferência e melhor carregamento inicial, sem promessa de nota fixa. Ganhos serão demonstrados após publicação e nova medição. Cache precisa distinguir arquivos com hash/versionados de arquivos de nome fixo. A mudança da lista expansível de contas a pagar seguirá separada, para não confundir regressões ou resultados.

Não há alteração de banco, regra financeira, credencial, tenant ou flag de IA. O titular aprovou o plano em 07/10/2026. Aprovação não substitui testes, backup ou registro dos resultados efetivamente observados.

Execução publicada em 07/10/2026 (2b434ec). Mediana mobile: desempenho 91, SEO/acessibilidade/boas práticas 100; LCP 2,6 s. Meta de LCP e integração no main pendentes. Ver relatório de validação.
