# MCP Hostinger no Cursor

O servidor MCP da Hostinger permite que o Cursor use a API da Hostinger (domínios, hospedagem, etc.) via ferramentas no chat.

## Configuração no projeto

- **`.cursor/mcp.json`** – config ativa (com sua API token). **Não é commitado** (está no `.gitignore`).
- **`.cursor/mcp.json.example`** – exemplo sem token, para outros devs.

## Usar em outra máquina ou novo clone

1. Copie o exemplo e preencha o token:
   ```bash
   cp .cursor/mcp.json.example .cursor/mcp.json
   ```
2. Edite `.cursor/mcp.json` e troque `ENTER_TOKEN_HERE` pela sua [API Token da Hostinger](https://hpanel.hostinger.com/account-api-tokens).

## Onde o Cursor lê a config

- Se o Cursor suportar **MCP por projeto**, ele usa `.cursor/mcp.json` na raiz do repo.
- Caso contrário, adicione o servidor manualmente em **Cursor Settings → MCP** com o mesmo conteúdo (comando `npx`, args `hostinger-api-mcp@latest`, env `API_TOKEN`).

## Segurança

- Nunca commite `.cursor/mcp.json` (já está no `.gitignore`).
- Não compartilhe sua API token; gere uma nova no hPanel se suspeitar de vazamento.
