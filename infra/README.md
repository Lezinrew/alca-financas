# Infra — intenção de deploy

Esta pasta consolida a **narrativa** de como a plataforma é (e será) publicada. Os ficheiros concretos de orquestração e servidor encontram-se na **raiz** e em `docs/`, conforme a stack já adotada no repositório.

## O que o projeto assume hoje

- **Contêineres** para desenvolvimento: `docker-compose.yml` (backend + frontend; Supabase fica na cloud).  
- **Produção:** compose de produção referenciado na documentação existente (ex. `docker-compose.prod.yml` na raiz, quando usado) e **Nginx** como reverse proxy.  
- **Hospedagem alvo** típica: **VPS (ex.: Hostinger)** com Linux, Docker ou stack equivalente, TLS (Let’s Encrypt ou outro) e regras de firewall documentadas em `docs/SSL-SETUP-GUIDE.md`, `docs/SEGURANCA-SERVIDOR.md`, `docs/MCP-HOSTINGER.md` (se aplicável).

## Placeholder / futuro

- Terraform ou Ansible **não** estão no escopo mínimo desta pasta.  
- Quando a infra fôr “como código” no repo, adicionar subpastas (ex. `terraform/`, `ansible/`) e apontar daqui.  
- Manter **um** sítio de verdade para o procedimento de deploy: `docs/DEPLOY-GUIDE.md`, `docs/DEPLOY-DO-ZERO.md` ou o que a equipa adotar após leitura do runbook.

## Relação com outros ficheiros

| Recurso | Onde |
|---------|------|
| Compose dev | `docker-compose.yml` |
| Nginx (ex. prod) | ficheiros `nginx*.conf` / `nginx/` na raiz, conforme existentes |
| SSL / VPS | `docs/SSL-SETUP-GUIDE.md`, `scripts/setup-nginx-proxy.sh` |
| n8n por trás de Nginx | `docs/N8N-VPS-SETUP.md` |

*Sem credenciais nesta pasta. Variáveis: sempre `.env` local e segredos fora do Git.*
