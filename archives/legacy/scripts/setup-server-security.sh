#!/bin/bash

###############################################################################
# Script de Segurança do Servidor - Alça Finanças
# Protege contra ataques de força bruta SSH e melhora segurança geral
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔒 Configurando segurança do servidor...${NC}\n"

# 1. Instalar fail2ban
echo -e "${BLUE}📦 Instalando fail2ban...${NC}"
apt-get update -qq
apt-get install -y fail2ban ufw

# 2. Configurar fail2ban para SSH
echo -e "${BLUE}⚙️  Configurando fail2ban...${NC}"
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
# Tempo de banimento (1 hora)
bantime = 3600
# Janela de tempo para contar falhas (10 minutos)
findtime = 600
# Número máximo de tentativas antes do banimento
maxretry = 5
# Ação a tomar (banir IP e enviar email se configurado)
action = %(action_)s

[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
backend = %(sshd_backend)s
maxretry = 3
bantime = 7200
findtime = 600

[sshd-ddos]
enabled = true
port = ssh
logpath = %(sshd_log)s
backend = %(sshd_backend)s
maxretry = 10
findtime = 600
bantime = 3600
EOF

# 3. Iniciar e habilitar fail2ban
systemctl enable fail2ban
systemctl restart fail2ban

# 4. Configurar firewall UFW
echo -e "${BLUE}🔥 Configurando firewall (UFW)...${NC}"

# Permitir SSH (importante fazer antes de habilitar!)
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Habilitar firewall (modo não-interativo)
echo "y" | ufw enable

# 5. Melhorar configuração do SSH
echo -e "${BLUE}🔐 Melhorando configuração do SSH...${NC}"

# Backup da configuração atual
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d_%H%M%S)

# Aplicar configurações de segurança
cat >> /etc/ssh/sshd_config <<'EOF'

# Configurações de segurança adicionadas automaticamente
# Desabilitar login root por senha (manter apenas chave SSH se necessário)
# PermitRootLogin prohibit-password

# Limitar tentativas de login
MaxAuthTries 3
MaxStartups 10:30:60

# Desabilitar autenticação vazia
PermitEmptyPasswords no

# Desabilitar protocolo SSH v1 (antigo e inseguro)
Protocol 2

# Timeout de conexão
ClientAliveInterval 300
ClientAliveCountMax 2

# Desabilitar forwarding X11 (se não usar)
X11Forwarding no

# Logs mais detalhados
LogLevel VERBOSE
EOF

# 6. Corrigir erro do PAM (pam_lastlog.so)
echo -e "${BLUE}🔧 Verificando módulo PAM...${NC}"
if [ ! -f /usr/lib/security/pam_lastlog.so ] && [ -f /lib/x86_64-linux-gnu/security/pam_lastlog.so ]; then
    # Criar link simbólico se o arquivo existir em outro local
    mkdir -p /usr/lib/security
    ln -sf /lib/x86_64-linux-gnu/security/pam_lastlog.so /usr/lib/security/pam_lastlog.so 2>/dev/null || true
fi

# 7. Testar configuração SSH antes de reiniciar
echo -e "${BLUE}🧪 Testando configuração SSH...${NC}"
if sshd -t; then
    echo -e "${GREEN}✅ Configuração SSH válida${NC}"
    # No Ubuntu, o serviço é 'ssh', não 'sshd'
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || service ssh reload 2>/dev/null
else
    echo -e "${RED}❌ Erro na configuração SSH. Restaurando backup...${NC}"
    cp /etc/ssh/sshd_config.backup.* /etc/ssh/sshd_config
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || service ssh reload 2>/dev/null
    exit 1
fi

# 8. Verificar status dos serviços
echo -e "\n${BLUE}📊 Status dos serviços de segurança:${NC}"
echo -e "${GREEN}✅ fail2ban:${NC}"
systemctl status fail2ban --no-pager -l | head -5

echo -e "\n${GREEN}✅ UFW (Firewall):${NC}"
ufw status verbose

echo -e "\n${GREEN}✅ IPs banidos pelo fail2ban:${NC}"
fail2ban-client status sshd 2>/dev/null | grep "Banned IP list" || echo "Nenhum IP banido no momento"

# 9. Criar script de monitoramento de segurança
cat > /usr/local/bin/check-security.sh <<'EOF'
#!/bin/bash
echo "=== Status de Segurança ==="
echo ""
echo "🔒 fail2ban:"
systemctl is-active fail2ban && echo "✅ Ativo" || echo "❌ Inativo"
echo ""
echo "🔥 UFW:"
ufw status | head -2
echo ""
echo "🚫 IPs banidos:"
fail2ban-client status sshd 2>/dev/null | grep "Banned IP list" || echo "Nenhum IP banido"
echo ""
echo "📊 Tentativas de login SSH (últimas 10):"
grep "Failed password" /var/log/auth.log 2>/dev/null | tail -10 || echo "Nenhuma tentativa recente"
EOF

chmod +x /usr/local/bin/check-security.sh

echo -e "\n${GREEN}✅ Segurança configurada com sucesso!${NC}"
echo -e "\n${YELLOW}📝 Próximos passos recomendados:${NC}"
echo -e "1. Configure autenticação por chave SSH (mais seguro que senha)"
echo -e "2. Execute: /usr/local/bin/check-security.sh para verificar status"
echo -e "3. Monitore logs: tail -f /var/log/fail2ban.log"
echo -e "4. Para desbanir um IP: fail2ban-client set sshd unbanip <IP>"
echo -e "\n${GREEN}🔒 Servidor protegido contra ataques de força bruta!${NC}"

