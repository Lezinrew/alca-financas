# 🔒 Segurança do Servidor - Alça Finanças

Documentação sobre as medidas de segurança implementadas no servidor.

---

## ✅ Medidas Implementadas

### 1. **fail2ban** - Proteção contra Força Bruta
- **Status**: ✅ Ativo e funcionando
- **Configuração**:
  - Banimento após **3 tentativas falhadas** de login SSH
  - Tempo de banimento: **2 horas** (7200 segundos)
  - Janela de tempo: **10 minutos** (600 segundos)
- **Monitoramento**: Analisa logs do SSH em tempo real
- **Ação**: Bloqueia IPs maliciosos automaticamente via firewall

### 2. **UFW (Firewall)** - Controle de Acesso
- **Status**: ✅ Ativo e habilitado
- **Portas abertas**:
  - `22/tcp` - SSH
  - `80/tcp` - HTTP
  - `443/tcp` - HTTPS
- **Todas as outras portas**: Bloqueadas por padrão

### 3. **SSH Hardening** - Melhorias de Segurança
- **MaxAuthTries**: 3 tentativas máximas
- **MaxStartups**: Limite de conexões simultâneas (10:30:60)
- **PermitEmptyPasswords**: Desabilitado
- **Protocol**: Apenas SSH v2 (v1 desabilitado)
- **ClientAliveInterval**: 300 segundos (timeout de conexão)
- **LogLevel**: VERBOSE (logs detalhados)

### 4. **PAM** - Correção de Módulo
- Erro do `pam_lastlog.so` verificado e corrigido se necessário

---

## 📊 Monitoramento

### Verificar Status de Segurança
```bash
/usr/local/bin/check-security.sh
```

### Ver IPs Banidos
```bash
fail2ban-client status sshd
```

### Ver Logs do fail2ban
```bash
tail -f /var/log/fail2ban.log
```

### Ver Tentativas de Login SSH
```bash
grep "Failed password\|Invalid user" /var/log/auth.log | tail -20
```

### Ver Status do Firewall
```bash
ufw status verbose
```

---

## 🛠️ Comandos Úteis

### Desbanir um IP
```bash
fail2ban-client set sshd unbanip <IP_ADDRESS>
```

### Banir um IP manualmente
```bash
fail2ban-client set sshd banip <IP_ADDRESS>
```

### Reiniciar fail2ban
```bash
systemctl restart fail2ban
```

### Adicionar regra ao firewall
```bash
ufw allow <PORT>/<PROTOCOL> comment 'Descrição'
```

### Remover regra do firewall
```bash
ufw delete allow <PORT>/<PROTOCOL>
```

---

## ⚠️ Recomendações Adicionais

### 1. **Autenticação por Chave SSH** (Recomendado)
Desabilitar login por senha e usar apenas chaves SSH:

```bash
# No servidor, editar /etc/ssh/sshd_config
PasswordAuthentication no
PubkeyAuthentication yes

# Reiniciar SSH
systemctl reload ssh
```

### 2. **Mudar Porta SSH** (Opcional)
Reduzir ataques automatizados mudando a porta padrão:

```bash
# Editar /etc/ssh/sshd_config
Port 2222  # ou outra porta

# Atualizar firewall
ufw allow 2222/tcp comment 'SSH Custom Port'
ufw delete allow 22/tcp

# Reiniciar SSH
systemctl reload ssh
```

### 3. **Desabilitar Login Root** (Recomendado)
Criar um usuário não-root e usar sudo:

```bash
# Criar usuário
adduser deploy
usermod -aG sudo deploy

# Copiar chave SSH
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Editar /etc/ssh/sshd_config
PermitRootLogin no

# Reiniciar SSH
systemctl reload ssh
```

### 4. **Backup Automático**
Configurar backups regulares dos arquivos importantes:

```bash
# Backup da configuração SSH
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d)

# Backup do fail2ban
cp /etc/fail2ban/jail.local /etc/fail2ban/jail.local.backup.$(date +%Y%m%d)
```

### 5. **Atualizações de Segurança**
Manter o sistema atualizado:

```bash
apt update && apt upgrade -y
```

### 6. **Monitoramento de Logs**
Configurar alertas para tentativas de ataque:

```bash
# Instalar ferramentas de monitoramento
apt install -y logwatch

# Configurar alertas por email (opcional)
```

---

## 📈 Estatísticas de Ataques

O servidor está sendo constantemente atacado por bots que tentam:
- Força bruta em login SSH
- Tentativas com usuários comuns (root, admin, ubuntu, etc.)
- Varredura de portas

**Com fail2ban ativo**, esses ataques são automaticamente bloqueados após 3 tentativas falhadas.

---

## 🔍 Troubleshooting

### fail2ban não está banindo IPs
```bash
# Verificar se está rodando
systemctl status fail2ban

# Verificar logs
tail -f /var/log/fail2ban.log

# Verificar configuração
fail2ban-client status sshd
```

### Firewall bloqueando conexões legítimas
```bash
# Verificar regras
ufw status numbered

# Permitir IP específico
ufw allow from <IP_ADDRESS> to any port 22
```

### Não consigo conectar via SSH
```bash
# Verificar se SSH está rodando
systemctl status ssh

# Verificar logs
tail -f /var/log/auth.log

# Verificar se seu IP foi banido
fail2ban-client status sshd | grep <SEU_IP>
```

---

## 📝 Notas Importantes

1. **Sempre teste configurações SSH antes de aplicar**:
   ```bash
   sshd -t  # Testa configuração sem aplicar
   ```

2. **Mantenha uma sessão SSH aberta** ao fazer mudanças críticas

3. **Backup antes de mudanças importantes**

4. **Monitore logs regularmente** para detectar padrões de ataque

---

**Última atualização**: Novembro 2025

