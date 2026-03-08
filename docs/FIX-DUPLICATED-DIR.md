# Fix: Diretório duplicado após git clone

Se você executou os comandos antigos e acabou com `/var/www/alca-financas/alca-financas`, use este guia para corrigir.

## Problema

Você tem:
```
/var/www/alca-financas/
└── alca-financas/    ← repositório clonado aqui (ERRADO)
    ├── backend/
    ├── frontend/
    └── ...
```

Deveria ser:
```
/var/www/alca-financas/    ← repositório clonado aqui (CERTO)
├── backend/
├── frontend/
└── ...
```

## Solução Rápida (Copiar e Colar)

### Opção 1: Mover conteúdo para o diretório pai

```bash
ssh root@SEU_IP_VPS

# Verificar a estrutura atual
ls -la /var/www/alca-financas/
ls -la /var/www/alca-financas/alca-financas/

# Mover todo o conteúdo para o diretório pai
cd /var/www/alca-financas
mv alca-financas/* .
mv alca-financas/.* . 2>/dev/null || true

# Remover o diretório vazio
rmdir alca-financas

# Verificar que ficou correto
ls -la /var/www/alca-financas/
```

### Opção 2: Remover tudo e reclonar corretamente

```bash
ssh root@SEU_IP_VPS

# Backup do .env se já existir
[ -f /var/www/alca-financas/alca-financas/.env ] && \
  cp /var/www/alca-financas/alca-financas/.env /tmp/alca-backup.env

# Remover tudo
rm -rf /var/www/alca-financas/*
rm -rf /var/www/alca-financas/.*  2>/dev/null || true

# Clonar corretamente (com ponto no final!)
cd /var/www/alca-financas
git clone https://github.com/Lezinrew/alca-financas.git .

# Restaurar .env se houver backup
[ -f /tmp/alca-backup.env ] && \
  mv /tmp/alca-backup.env /var/www/alca-financas/.env

# Verificar
ls -la /var/www/alca-financas/
```

## Verificação

Depois de corrigir, você deve ver isto:

```bash
ssh root@SEU_IP_VPS "ls -la /var/www/alca-financas/"

# Saída esperada:
drwxr-xr-x  10 root root 4096 Mar  5 10:00 .
drwxr-xr-x   4 root root 4096 Mar  5 09:00 ..
drwxr-xr-x   8 root root 4096 Mar  5 10:00 .git       ← deve estar aqui
-rw-r--r--   1 root root  123 Mar  5 10:00 .env
drwxr-xr-x   3 root root 4096 Mar  5 10:00 backend    ← deve estar aqui
drwxr-xr-x   5 root root 4096 Mar  5 10:00 frontend   ← deve estar aqui
-rw-r--r--   1 root root 1234 Mar  5 10:00 docker-compose.prod.yml
...
```

**NÃO deve ter** uma pasta `alca-financas` dentro de `/var/www/alca-financas/`.

## Depois de corrigir

Agora você pode rodar o deploy normalmente:

```bash
# Na sua máquina local
cd /caminho/para/alca-financas

export SERVER_HOST="SEU_IP_VPS"
export SERVER_USER="root"
export PROJECT_DIR="/var/www/alca-financas"
export DOMAIN="alcahub.cloud"

./scripts/deploy-docker-remote.sh
```

O script já foi corrigido e não vai mais criar diretório duplicado!
