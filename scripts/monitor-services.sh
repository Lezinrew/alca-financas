#!/bin/bash
# Script de monitoramento básico dos serviços

set -e

SERVER_HOST="alcahub.com.br"
SERVER_USER="root"

echo "📊 Monitoramento de Serviços - Alca Finanças"
echo "=============================================="
echo ""

sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<'EOF'
    echo "🔍 Status dos Serviços:"
    echo ""
    
    # Backend
    echo "1. Backend API (alca-financas):"
    systemctl is-active --quiet alca-financas && echo "   ✅ Ativo" || echo "   ❌ Inativo"
    systemctl status alca-financas --no-pager -l | grep -E "(Active|Main PID|Memory|CPU)" | head -4 | sed 's/^/   /'
    echo ""
    
    # Chatbot
    echo "2. Chatbot (alca-chatbot):"
    systemctl is-active --quiet alca-chatbot && echo "   ✅ Ativo" || echo "   ❌ Inativo"
    systemctl status alca-chatbot --no-pager -l | grep -E "(Active|Main PID|Memory|CPU)" | head -4 | sed 's/^/   /'
    echo ""
    
    # Nginx
    echo "3. Nginx:"
    systemctl is-active --quiet nginx && echo "   ✅ Ativo" || echo "   ❌ Inativo"
    systemctl status nginx --no-pager -l | grep -E "(Active|Main PID|Memory|CPU)" | head -4 | sed 's/^/   /'
    echo ""
    
    # MongoDB
    echo "4. MongoDB:"
    systemctl is-active --quiet mongod 2>/dev/null && echo "   ✅ Ativo" || echo "   ⚠️  Status desconhecido (pode estar rodando localmente)"
    echo ""
    
    echo "🌐 Health Checks:"
    echo ""
    
    # API Health
    echo -n "   API: "
    curl -s -o /dev/null -w "%{http_code}" https://api.alcahub.com.br/api/health | grep -q "200" && echo "✅ OK" || echo "❌ Erro"
    
    # Chatbot Health
    echo -n "   Chatbot: "
    curl -s -o /dev/null -w "%{http_code}" https://chat.alcahub.com.br/api/health | grep -q "200" && echo "✅ OK" || echo "❌ Erro"
    
    # Frontend
    echo -n "   Frontend: "
    curl -s -o /dev/null -w "%{http_code}" https://app.alcahub.com.br | grep -q "200" && echo "✅ OK" || echo "❌ Erro"
    
    echo ""
    echo "💾 Uso de Disco:"
    df -h / | tail -1 | awk '{print "   Uso: " $5 " (" $3 " de " $2 ")"}'
    
    echo ""
    echo "🧠 Uso de Memória:"
    free -h | grep Mem | awk '{print "   Total: " $2 " | Usado: " $3 " | Livre: " $4}'
    
    echo ""
    echo "📈 Últimos Logs (Backend - últimas 5 linhas):"
    journalctl -u alca-financas -n 5 --no-pager | tail -5 | sed 's/^/   /'
EOF

echo ""
echo "✅ Monitoramento concluído!"

