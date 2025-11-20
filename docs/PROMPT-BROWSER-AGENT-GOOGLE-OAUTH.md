# 🤖 Prompt para Browser Agent - Configurar Google OAuth

Use este prompt com o Atlas Browser Agent (ou similar) para configurar automaticamente o Google OAuth para o Alça Finanças.

---

## 📋 Prompt Completo

```
Você é um assistente especializado em configurar OAuth 2.0 no Google Cloud Console.

OBJETIVO:
Configurar autenticação OAuth do Google para a aplicação "Alça Finanças" que roda em:
- Domínio de produção: https://alcahub.com.br
- API endpoint: https://api.alcahub.com.br
- Callback URL: https://api.alcahub.com.br/api/auth/google/callback

TAREFAS A EXECUTAR (em ordem):

1. NAVEGAR PARA GOOGLE CLOUD CONSOLE
   - Acesse: https://console.cloud.google.com/
   - Faça login com a conta Google fornecida (se necessário)
   - Aguarde o carregamento completo da página

2. CRIAR OU SELECIONAR PROJETO
   - Se não houver projeto, clique em "Selecionar projeto" → "NOVO PROJETO"
   - Nome do projeto: "Alca Finanças" (ou "Alca Financas" se caracteres especiais não forem aceitos)
   - Clique em "CRIAR" e aguarde a criação
   - Se já existir projeto, selecione-o

3. CONFIGURAR TELA DE CONSENTIMENTO OAUTH
   - No menu lateral esquerdo, clique em "APIs e Serviços"
   - Clique em "Tela de consentimento OAuth"
   - Se for a primeira vez, selecione "Externo" e clique em "CRIAR"
   - Preencha os campos obrigatórios:
     * Nome do aplicativo: "Alça Finanças"
     * Email de suporte do usuário: [use o email fornecido ou lezinrew@gmail.com]
     * Email de contato do desenvolvedor: [mesmo email acima]
   - Clique em "SALVAR E CONTINUAR"
   - Na etapa "Escopos", clique em "SALVAR E CONTINUAR" (sem adicionar escopos)
   - Na etapa "Usuários de teste", se solicitado, adicione o email de teste e clique em "SALVAR E CONTINUAR"
   - Na etapa "Resumo", clique em "VOLTAR AO PAINEL"

4. CRIAR CREDENCIAIS OAUTH 2.0
   - No menu lateral, vá em "APIs e Serviços" → "Credenciais"
   - Clique no botão "+ CRIAR CREDENCIAIS" (ou "Create Credentials")
   - Selecione "ID do cliente OAuth" (ou "OAuth client ID")
   - Se solicitado, selecione "Aplicativo da Web" (ou "Web application")
   - Preencha:
     * Nome: "Alca Finanças Web Client"
     * URIs de redirecionamento autorizados (Authorized redirect URIs):
       - https://api.alcahub.com.br/api/auth/google/callback
       - https://alcahub.com.br/api/auth/google/callback
       - http://localhost:8001/api/auth/google/callback
     * (Adicione cada URI em uma linha separada)
   - Clique em "CRIAR" (ou "Create")
   - AGUARDE a exibição do modal/popup com as credenciais

5. CAPTURAR E EXIBIR CREDENCIAIS
   - Copie o "ID do cliente" (Client ID) - formato: xxx.apps.googleusercontent.com
   - Copie o "Segredo do cliente" (Client secret) - formato: GOCSPX-xxx
   - ⚠️ IMPORTANTE: O segredo só aparece uma vez! Certifique-se de capturá-lo.
   - Exiba claramente no formato:
     ```
     GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=GOCSPX-xxx
     ```
   - Salve essas credenciais em um arquivo temporário ou exiba de forma destacada

6. VERIFICAR CONFIGURAÇÃO
   - Volte para "Credenciais" e confirme que o novo ID do cliente aparece na lista
   - Verifique se as URIs de redirecionamento estão corretas

INSTRUÇÕES ESPECIAIS:
- Se encontrar qualquer erro ou página não encontrada, informe imediatamente
- Se o Google solicitar verificação adicional (ex: domínio), informe o usuário
- Se já existirem credenciais OAuth, você pode reutilizá-las ou criar novas (informe ao usuário)
- Se o idioma da interface for inglês, adapte os nomes dos botões/menus conforme necessário
- Tire screenshots das etapas críticas (especialmente quando as credenciais são exibidas)

FORMATO DE SAÍDA ESPERADO:
Ao finalizar, exiba:
1. ✅ Status de cada etapa (concluída ou erro)
2. 📋 Credenciais geradas (GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET)
3. ⚠️ Próximos passos: informar que o usuário precisa adicionar essas credenciais no arquivo .env do servidor
```

---

## 🎯 Versão Resumida (Prompt Curto)

```
Configure OAuth 2.0 no Google Cloud Console para "Alça Finanças":
1. Acesse console.cloud.google.com e crie/selecione projeto "Alca Financas"
2. Configure Tela de Consentimento OAuth (Externo, nome: "Alça Finanças")
3. Crie credenciais OAuth 2.0 (Web application) com URIs:
   - https://api.alcahub.com.br/api/auth/google/callback
   - https://alcahub.com.br/api/auth/google/callback
   - http://localhost:8001/api/auth/google/callback
4. Capture e exiba GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET
5. Informe que essas credenciais devem ser adicionadas em /var/www/alca-financas/backend/.env
```

---

## 📝 Como Usar

1. **Copie o prompt completo** acima
2. **Cole no Browser Agent** (Atlas, Cursor Browser, etc.)
3. **Execute** e acompanhe as etapas
4. **Salve as credenciais** exibidas
5. **Configure no servidor** usando o comando abaixo:

```bash
ssh root@alcahub.com.br
nano /var/www/alca-financas/backend/.env
# Adicione as linhas:
# GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
# GOOGLE_CLIENT_SECRET=GOCSPX-xxx
systemctl restart alca-financas
```

---

## ⚠️ Avisos Importantes

- O **Client Secret** só aparece **uma vez** após a criação
- **Nunca** commite essas credenciais no Git
- Mantenha as credenciais em local seguro
- Se perder o secret, será necessário regenerar no Google Cloud Console

