# 🤖 Configuração do Chatbot OpenClaw

Guia completo para integrar o OpenClaw (chatbot com IA) ao Alça Finanças.

## 📋 Pré-requisitos

- ✅ OpenClaw instalado na Hostinger
- ✅ Gateway Token do OpenClaw
- ✅ Anthropic API Key (Claude AI)
- ✅ URL do OpenClaw via Traefik

## 🔧 Configuração

### 1️⃣ Variáveis de Ambiente do OpenClaw (Hostinger)

No painel da Hostinger, adicione/configure estas variáveis para o container do OpenClaw:

```env
PORT=40394
TZ=America/Sao_Paulo
OPENCLAW_GATEWAY_TOKEN=seu-gateway-token-aqui
ANTHROPIC_API_KEY=sk-ant-api03-seu-anthropic-api-key-aqui
WHATSAPP_NUMBER=+5531999675817
TRAEFIK_HOST=srv1353242.hstgr.cloud
```

### 2️⃣ Variáveis de Ambiente do Backend

Adicione no `.env` do backend (tanto local quanto produção):

```env
# OpenClaw Chatbot
OPENCLAW_GATEWAY_TOKEN=YOUR_GATEWAY_TOKEN_HERE
OPENCLAW_URL=https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud
```

**Para produção (Hostinger):**
Adicione essas mesmas variáveis no painel Docker da Hostinger para o container do backend.

### 3️⃣ Verificar URL do OpenClaw

O OpenClaw deve estar acessível em:
```
https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud
```

Para verificar se está funcionando, acesse:
```bash
curl https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud/health
```

Se não estiver acessível, verifique:
1. O container está rodando: `docker ps | grep openclaw`
2. Traefik está configurado corretamente
3. Certificado SSL está OK

### 4️⃣ Adicionar Componente no Frontend

O componente `Chatbot.tsx` já foi criado. Agora adicione-o no layout principal da aplicação.

**Edite** `frontend/src/App.tsx` ou o arquivo de layout principal:

```tsx
import { Chatbot } from './components/Chatbot';

function App() {
  return (
    <div>
      {/* Seu conteúdo existente */}

      {/* Adicione o chatbot no final */}
      <Chatbot />
    </div>
  );
}
```

### 5️⃣ Testar Localmente

1. **Iniciar o backend**:
```bash
cd backend
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
python app.py
```

2. **Iniciar o frontend**:
```bash
cd frontend
npm run dev
```

3. **Testar o chatbot**:
   - Abra http://localhost:3000
   - Faça login
   - Clique no botão de chat no canto inferior direito
   - Envie uma mensagem de teste

### 6️⃣ Deploy em Produção

1. **Commitar as mudanças**:
```bash
git add .
git commit -m "feat: integrate OpenClaw chatbot"
git push origin main
```

2. **Atualizar no servidor VPS**:
```bash
ssh alcaapp@76.13.239.220
cd /home/alcaapp/alca-financas

# Pull das mudanças
git pull origin main

# Atualizar .env do backend com as variáveis do OpenClaw
nano backend/.env
# Adicione:
# OPENCLAW_GATEWAY_TOKEN=YOUR_GATEWAY_TOKEN_HERE
# OPENCLAW_URL=https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud

# Reiniciar serviços (ajuste conforme sua configuração)
sudo systemctl restart alca-backend
sudo systemctl restart alca-frontend
# OU se estiver usando Docker:
# docker-compose -f docker-compose.prod.yml restart backend frontend
```

3. **Ou atualizar via Hostinger (se usando Docker Compose)**:
   - No painel da Hostinger, adicione as variáveis de ambiente do OpenClaw
   - Reinicie os containers

## 📡 Endpoints da API

O backend agora expõe estes endpoints:

### POST /api/chatbot/chat
Envia mensagem para o chatbot

**Request:**
```json
{
  "message": "Como criar uma transação?",
  "conversation_id": "optional-conv-id"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Para criar uma transação...",
  "conversation_id": "conv-123",
  "metadata": {}
}
```

### GET /api/chatbot/conversations/{conversation_id}
Busca histórico de uma conversa

**Response:**
```json
{
  "success": true,
  "history": [...]
}
```

### GET /api/chatbot/health
Verifica se o chatbot está disponível

**Response:**
```json
{
  "available": true
}
```

## 🎨 Personalização

### Customizar Mensagens do Bot

Edite `backend/services/openclaw_service.py` para customizar as mensagens de erro ou comportamento.

### Customizar UI do Chatbot

Edite `frontend/src/components/Chatbot.tsx` para alterar:
- Cores e estilos
- Posição do botão flutuante
- Tamanho da janela de chat
- Mensagens iniciais

### Adicionar Contexto Financeiro

Para que o bot entenda melhor sobre finanças, você pode:

1. **Criar um prompt system** no OpenClaw com informações sobre a aplicação
2. **Adicionar contexto nas mensagens** enviadas ao bot (dados do usuário, transações recentes, etc.)

Exemplo em `backend/services/openclaw_service.py`:

```python
def chat(self, message: str, user_id: str, conversation_id: Optional[str] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
    payload = {
        'message': message,
        'user_id': user_id,
        'context': context or {}  # Adicionar contexto aqui
    }
    # ...
```

## 🧪 Teste de Integração

Execute este teste manual:

1. Acesse a aplicação
2. Faça login
3. Clique no botão de chat
4. Envie: "Olá, como você pode me ajudar?"
5. Envie: "Como criar uma transação?"
6. Envie: "Qual a diferença entre receita e despesa?"

O bot deve responder com informações relevantes sobre o sistema.

## 🚨 Troubleshooting

### Bot não responde

**Verificar:**
```bash
# 1. OpenClaw está rodando?
curl https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud/health

# 2. Token está correto?
echo $OPENCLAW_GATEWAY_TOKEN

# 3. Ver logs do backend
tail -f /var/log/alca-backend.log | grep openclaw

# 4. Ver logs do OpenClaw
docker logs openclaw-qi3v-openclaw-1
```

### Timeout ao enviar mensagem

- Aumentar o timeout em `backend/services/openclaw_service.py`:
  ```python
  self.timeout = 60  # 60 segundos
  ```

### Erro 401 (Unauthorized)

- Verificar se `OPENCLAW_GATEWAY_TOKEN` está correto
- Verificar se o token não expirou

### Erro de CORS

- Adicionar domínio do OpenClaw no CORS do backend se necessário

## 📚 Recursos

- [Documentação OpenClaw](https://github.com/hostinger/hvps-openclaw)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Hostinger VPS Docs](https://support.hostinger.com/en/collections/3425965-vps)

## ✅ Checklist de Configuração

- [ ] OpenClaw instalado e rodando na Hostinger
- [ ] Gateway Token obtido
- [ ] Variáveis de ambiente configuradas no OpenClaw
- [ ] Variáveis de ambiente configuradas no backend
- [ ] Componente Chatbot adicionado no frontend
- [ ] Rotas de API testadas
- [ ] Chatbot funcional em desenvolvimento
- [ ] Deploy em produção realizado
- [ ] Testes de integração realizados

---

**Status**: ✅ Configuração completa

**Última atualização**: 2026-03-05
