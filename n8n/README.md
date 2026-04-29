# n8n no ecossistema Alça Finanças

Esta pasta na raiz **não** contém, por padrão, as exportações JSON dos fluxos. Serve para documentar o **papel** do n8n e a relação com o resto do sistema. Os workflows e o `docker-compose` do n8n costumam viver no **VPS** (ou outro host dedicado) por decisão operacional.

## Papel do n8n

- **Orquestração e automação** (webhooks, agendamentos, integrações de terceiros) sem encher o backend Flask de jobs assíncronos.  
- **Ponte com canais** como bots ou notificações, quando a lógica é visual e muda com frequência.  
- **Não** é o banco de verdade: dados financeiros continuam no **Supabase** e a API em `backend/`.

## Integração com o chatbot

- O chatbot do produto (rotas `backend/routes/chatbot` e, quando ativo, **OpenClaw**) conversa com o utilizador **dentro** da aplicação.  
- O **n8n** pode encadear ações *depois* ou *em paralelo* a eventos (ex.: enviar lembrete, chamar URL), desde que o contrato (payload, auth) fique claro.  
- Não há no repositório um contrato rígido único: cada workflow define os seus nós. Para segurança, use URLs com segredo e, quando possível, chame a API com o mesmo modelo de autenticação documentado em `docs/ENVIRONMENTS.md`.

## Integração com o backend

- O backend expõe REST em `/api/...` (ver `system-design.md`).  
- Workflows n8n podem usar **HTTP Request** para esses endpoints se **autenticados** (tokens de serviço / JWT conforme a política da equipa — **não** colocar service role no browser; seguir práticas de `docs/ENVIRONMENTS.md`).  
- **Webhooks de entrada** (n8n a receber POST) úteis para: integrações, bots, IFTTT-like, sem alterar a API principal.

## Onde fica a config “real”

- Guia de VPS, Nginx e SSL: **[docs/N8N-VPS-SETUP.md](../docs/N8N-VPS-SETUP.md)**.  
- Script de exemplo: `scripts/setup-n8n-nginx-ssl.sh` (domínio, Certbot, variáveis `N8N_HOST`, `WEBHOOK_URL`, etc.).  
- Em alguns diagnósticos legados, caminhos no servidor referem-se a `/docker/n8n` — ajuste ao teu host.

## Resumo

| Componente | Relação com n8n |
|------------|-----------------|
| Supabase | Fonte de dados; n8n não substitui migrations nem RLS |
| Backend Flask | API consumível via HTTP; rate limits aplicam |
| OpenClaw / chat | Diferente do n8n; complementar |
| Agente/LLM (produto) | UI + API; n8n é camada de automação externa |
