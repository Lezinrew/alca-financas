#!/bin/bash
# Script para configurar monitoramento básico com logrotate e limpeza automática

set -e

SERVER_HOST="alcahub.com.br"
SERVER_USER="root"

echo "📊 Configurando monitoramento e logs..."

sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<'EOF'
    # Criar diretório de logs se não existir
    mkdir -p /var/log/alca-financas
    
    # Configurar logrotate para os serviços
    cat > /etc/logrotate.d/alca-financas <<LOGROTATEEOF
/var/log/alca-financas/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload alca-financas > /dev/null 2>&1 || true
        systemctl reload alca-chatbot > /dev/null 2>&1 || true
    endscript
}

/var/www/alca-financas/backend/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
LOGROTATEEOF

    # Criar script de limpeza automática
    cat > /usr/local/bin/alca-cleanup.sh <<CLEANUPEOF
#!/bin/bash
# Limpeza automática de logs e cache antigos

# Limpar logs antigos (mais de 30 dias)
find /var/log/alca-financas -name "*.log.*" -mtime +30 -delete 2>/dev/null || true

# Limpar cache do sistema (opcional)
# apt-get clean 2>/dev/null || true

# Limpar arquivos temporários
find /tmp -name "alca-*" -mtime +7 -delete 2>/dev/null || true

echo "$(date): Limpeza automática executada" >> /var/log/alca-financas/cleanup.log
CLEANUPEOF

    chmod +x /usr/local/bin/alca-cleanup.sh
    
    # Adicionar ao crontab (executar diariamente às 2h da manhã)
    (crontab -l 2>/dev/null | grep -v "alca-cleanup.sh"; echo "0 2 * * * /usr/local/bin/alca-cleanup.sh") | crontab -
    
    echo "✅ Monitoramento configurado"
    echo "   - Logrotate configurado"
    echo "   - Limpeza automática agendada (diariamente às 2h)"
EOF

echo "✅ Configuração de monitoramento concluída!"

