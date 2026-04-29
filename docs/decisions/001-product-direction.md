# ADR 001 — Direção de produto

**Status:** aceite  
**Contexto:** Alça Finanças como plataforma SaaS multi-tenant de finanças com extensão por IA e automação.

## Objetivo do produto

Oferecer **visibilidade e controlo** sobre o dinheiro (entradas, saídas, contas, categorias) com **trabalho em equipa por organização** (tenant) e com caminhos naturais para **planejamento**, **metas** e **despesas recorrentes**, sem depender de planilhas como fonte de verdade.

## Público alvo

- **Pequenos negócios e equipas** que partilham o mesmo “livro” financeiro.  
- **Pessoas singulares** com múltiplas contas e necessidade de relatórios e importação.  
- **Utilizadores técnicos** (ou parceiros) que podem integrar **chat** e **n8n** para notificações e fluxos customizados.

## Visão de longo prazo

- **Um núcleo financeiro sólido** (transações, contas, categorias, multi-tenant, segurança RLS) como base.  
- **Canais de interação** (web forte; mobile a crescer; automações e assistentes por cima).  
- **Operação previsível**: migrations versionadas, CI, documentação mínima para retomar o serviço sem conhecimento oral.

## Diferenciais (chatbot + finanças)

- **Assistente no contexto da aplicação:** rotas e serviços de chat ligados à mesma identidade e API que a UI — não “chat genérico” desligado do saldo e das regras.  
- **Dois modos de IA/automação no ecossistema:** (1) serviço de regras `services/chatbot`, (2) **OpenClaw** opcional para LLM com `tenant`/utilizador no fluxo, quando configurado.  
- **n8n** para integrações de longa duração (webhooks, canais) sem colocar toda a lógica no backend síncrono.

Esta visão restringe-se ao que o repositório **suporta ou documenta**; funcionalidades futuras exigem novo ADR ou evolução deste.
