
# 📋 Passo a Passo: Adicionar IP na Whitelist do MongoDB Atlas

Este guia mostra como adicionar o IP do servidor (`77.37.43.126`) na whitelist do MongoDB Atlas para permitir conexões.

---

## 🎯 Objetivo

Adicionar o IP `77.37.43.126` na lista de IPs autorizados do MongoDB Atlas para que o servidor possa se conectar ao banco de dados.

---

## 📝 Passo a Passo

### Passo 1: Acessar o MongoDB Atlas

1. Abra seu navegador e acesse: **https://cloud.mongodb.com/**
2. Faça login com sua conta do MongoDB Atlas
3. Você será redirecionado para o dashboard

---

### Passo 2: Navegar até Network Access

1. No menu lateral esquerdo, procure por **"Security"** (Segurança)
2. Clique em **"Network Access"** (ou "Acesso à Rede")
   - Alternativamente, você pode ver um ícone de escudo 🔒 ou cadeado no menu
   - O texto pode estar em português como "Acesso à Rede" ou "Acesso de Rede"

**Localização alternativa:**
- Algumas versões do MongoDB Atlas têm o menu "Network Access" diretamente no menu principal
- Procure por um item chamado "Network Access", "IP Access List" ou "Whitelist"

---

### Passo 3: Adicionar Novo IP

1. Na página "Network Access", você verá uma lista de IPs já autorizados (se houver)
2. Clique no botão **"Add IP Address"** (ou "Adicionar Endereço IP")
   - O botão geralmente está no canto superior direito
   - Pode aparecer como um botão verde ou azul com um ícone de "+"

---

### Passo 4: Configurar o IP

Você terá duas opções:

#### Opção A: Adicionar IP Específico (Recomendado para Produção)

1. Selecione **"Add Current IP Address"** (se estiver acessando do servidor) OU
2. Selecione **"Add IP Address"** e digite manualmente:
   - **IP Address:** `77.37.43.126`
   - **Comment (opcional):** `Alca Financas Server` ou `Servidor Alca Financas`
3. Clique em **"Confirm"** (Confirmar)

#### Opção B: Permitir Qualquer IP (Apenas para Teste)

⚠️ **ATENÇÃO:** Use esta opção apenas para testes. Não é recomendado para produção.

1. Selecione **"Allow Access from Anywhere"** (Permitir acesso de qualquer lugar)
2. Isso adicionará `0.0.0.0/0` na lista
3. Clique em **"Confirm"**

**Recomendação:** Use a Opção A para maior segurança.

---

### Passo 5: Verificar

1. Após clicar em "Confirm", o IP `77.37.43.126` deve aparecer na lista
2. O status deve mostrar como **"Active"** (Ativo)
3. Pode levar alguns segundos para o status mudar de "Pending" para "Active"

---

### Passo 6: Testar Conexão

Após adicionar o IP, o backend deve conseguir conectar automaticamente. Você pode verificar:

1. **Verificar logs do backend:**
   ```bash
   ssh root@alcahub.com.br 'journalctl -u alca-financas -n 20 --no-pager'
   ```

2. **Testar login com Google:**
   - Acesse: https://alcahub.com.br/login
   - Clique em "Continuar com Google"
   - O erro 502 deve desaparecer

---

## 🔍 Verificando se Funcionou

### Método 1: Verificar Logs do Backend

Execute no terminal local:

```bash
./scripts/check-backend-status.sh
```

Procure por mensagens de sucesso na conexão com MongoDB.

### Método 2: Testar Login

1. Acesse https://alcahub.com.br/login
2. Clique em "Continuar com Google"
3. Se funcionar, você será redirecionado para o Google e depois de volta para o dashboard

---

## ❌ Problemas Comuns

### Problema 1: Não consigo encontrar "Network Access"

**Solução:**
- Procure por "Security" no menu lateral
- Ou procure por "IP Access List"
- Algumas versões têm um menu "Access Control" que contém "Network Access"

### Problema 2: O IP foi adicionado mas ainda não funciona

**Soluções:**
1. Aguarde 1-2 minutos (pode levar tempo para propagar)
2. Verifique se o IP está correto: `77.37.43.126`
3. Verifique se o status está como "Active" (não "Pending")
4. Reinicie o serviço backend:
   ```bash
   ssh root@alcahub.com.br 'systemctl restart alca-financas'
   ```

### Problema 3: Erro "IP not whitelisted"

**Solução:**
- Verifique se digitou o IP corretamente
- Certifique-se de que o status está "Active"
- Tente adicionar `0.0.0.0/0` temporariamente para teste

---

## 🔒 Segurança

### Boas Práticas:

1. ✅ **Use IPs específicos** em produção (não `0.0.0.0/0`)
2. ✅ **Remova IPs não utilizados** da whitelist
3. ✅ **Adicione comentários** para identificar cada IP
4. ✅ **Revise a lista periodicamente**

### IPs que você pode precisar adicionar:

- **Servidor de produção:** `77.37.43.126` ✅ (já identificado)
- **Seu IP local** (para desenvolvimento/testes): Verifique com `curl ifconfig.me`
- **Outros servidores** (se houver)

---

## 📞 Suporte

Se após seguir todos os passos o problema persistir:

1. Verifique os logs do backend
2. Verifique se o MONGO_URI está correto no `.env`
3. Verifique se o usuário e senha do MongoDB estão corretos
4. Entre em contato com o suporte do MongoDB Atlas se necessário

---

## ✅ Checklist

Use este checklist para garantir que tudo está configurado:

- [ ] Acessei o MongoDB Atlas
- [ ] Naveguei até "Network Access"
- [ ] Adicionei o IP `77.37.43.126`
- [ ] O IP aparece como "Active"
- [ ] Testei a conexão do backend
- [ ] Testei o login com Google
- [ ] Tudo está funcionando! 🎉

---

**Última atualização:** 24/11/2025

