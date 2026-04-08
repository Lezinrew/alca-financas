# Prompt — Site de apresentação Alça Finanças (Hostinger + vibe coding)

Use este texto no **assistente de IA da Hostinger** (Website Builder / Horizons), ou cole num editor com IA, para gerar o **site institucional de uma página + páginas secundárias** do produto **Alça Finanças**. Ajuste URLs e domínio finais antes de publicar.

---

## Texto do prompt (copiar daqui)

```
És um designer front-end e redator de produto. Vais construir o site principal de apresentação do "Alça Finanças" — aplicação web de controle financeiro pessoal (receitas, despesas, contas, categorias, importação CSV, dashboard com gráficos, auth segura com Supabase).

Stack de referência do produto (para copy técnica opcional): React, PWA-ready, responsivo. O site de apresentação NÃO precisa de replicar a app; deve convencer e levar ao registo/login.

### Estilo: vibe coding (obrigatório)
- Evita o visual genérico "AI slop": nada de Inter/Roboto no centro com três cards iguais e fundo cinzento.
- Escolhe UMA direção visual forte e consistente (ex.: editorial escuro com acento metálico; ou brutalist com tipografia gigante; ou retro-futurista com grid e ruído). Alterna bem claro/escuro ou commit a um tema dominante.
- Tipografia: importa do Google Fonts DOIS fontes — uma display com personalidade + uma body legível (proíbe usar só Inter, Roboto, Arial, Space Grotesk como protagonistas).
- Cor: paleta com CSS variables; 1 cor de acento nítida; contraste acessível (WCAG AA nas áreas de texto).
- Layout: assimétria, overlap, ou grid quebrado — não uma pilha de cards centrada previsível.
- Profundidade: gradientes em camadas, grain/noise leve, sombras dramáticas OU flat maximalista — mas intencional.
- Motion: entrada em stagger, hover surpreendente em CTAs, micro-interações em secções (CSS ou pouco JS).
- Imagens: placeholders com gradiente/abstract shapes até haver fotos reais; se houver mockups, referir "dashboard" de forma sugestiva.

### Conteúdo e estrutura (página inicial)
1. Hero: headline curta em PT-BR (benefício: claridade financeira), sublinha, 2 CTAs — primário "Começar grátis" / secundário "Ver funcionalidades" (âncora).
2. Prova social leve: texto tipo "Feito para quem quer ver o dinheiro com clareza" + opcional contador/depoimento fictício editável depois.
3. Funcionalidades em 4–6 blocos com ícone ou número: transações, categorias, contas, import CSV, dashboard/gráficos, auth e segurança (sem jargão excessivo).
4. Secção "Como funciona" — 3 passos: criar conta → registar movimentos → ver painéis.
5. Secção técnica opcional (colapsável ou secção curta): "Privacidade e infra" — dados em PostgreSQL (Supabase), boas práticas; sem prometer o que não está no produto.
6. FAQ curto (3–5 perguntas): é gratuito? funciona no telemóvel? posso importar extratos? como recupero a senha?
7. CTA final repetido + rodapé com links: Privacidade, Termos (placeholders), Contacto, Github/projeto se existir.

### Páginas secundárias mínimas
- /precos ou /planos — se o produto for single-tier, uma página honesta "em evolução" com CTA para registo.
- /contato — formulário simples (nome, email, mensagem) ou email mailto.

### SEO e metadados
- title e meta description em PT-BR.
- headings hierárquicos (um H1 na home).
- Open Graph básico (título, descrição, imagem OG quando disponível).

### Integração Hostinger
- HTML semântico, CSS organizado (ou blocos do builder equivalentes).
- Formulários: apontar para mailto ou integração do builder; não inventar endpoints.
- Botões principais devem linkar para a URL REAL da app (substituir placeholder): FRONTEND_APP_URL = "https://alcahub.cloud" (ou o domínio final).
- Performance: imagens otimizadas, lazy load onde fizer sentido.

### Tom de voz
- Português do Brasil, claro, confiante, sem infantilizar.
- Evita hype vazio ("revolucionário"); privilegia benefícios mensuráveis (organização, visão mensal, categorias).

Entrega esperada: estrutura completa de index + CSS (e JS mínimo se necessário), lista de assets a substituir (logo, OG image), e notas de onde editar links e textos legais.
```

---

## Depois de gerar o site

Substituir no HTML/builder:

| Placeholder | Exemplo |
|-------------|---------|
| Link da app | `https://alcahub.cloud` (ou URL definitiva) |
| Email de contacto | O que usar em produção |
| Política de privacidade / termos | Páginas reais ou “em breve” com aviso |

## Relação com o repositório

O código da **aplicação** está neste repo (`alca-financas`). O site de **marketing** na Hostinger pode ser um **site estático separado** ou subdomínio (`www` marketing + `app` na aplicação), conforme a tua arquitetura de DNS.
