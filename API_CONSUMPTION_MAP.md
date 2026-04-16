# API Consumption Map - Frontend -> Backend Chatbot

## Escopo mapeado

- Frontend analisado: `frontend/src/components/chat/ChatWidget.tsx`, `frontend/src/components/Chatbot.tsx`, `frontend/src/utils/api.ts`.
- Backend de destino analisado: `backend/routes/chatbot.py`, `backend/app.py`, `backend/services/openclaw_service.py`.
- Observacao: o frontend hoje possui chamadas ativas e chamadas "catalogadas" em `chatbotAPI` (helper exportado, ainda sem uso direto encontrado).

## Matriz de consumo de API

| Arquivo de origem | Endpoint chamado no frontend | Metodo HTTP | Headers enviados | Precisa token? | Servico de destino | Possiveis riscos de CORS |
|---|---|---|---|---|---|---|
| `frontend/src/components/chat/ChatWidget.tsx` | `POST ${CHAT_HTTP_BASE}/chat` (`http://localhost:8001/api/chatbot/chat` em dev, `/api/chatbot/chat` em prod) | POST | `Authorization: Bearer <auth_token>` (manual), `Content-Type: application/json` (axios) | Sim (validado no frontend e exigido por `@token_required`) | Flask `backend/routes/chatbot.py` (`/api/chatbot/chat`) -> `OpenClawService.chat()` -> `openclaw-bridge` (`/chat`) -> gateway/LLM | **Dev:** cross-origin entre `localhost:5173` e `localhost:8001`, depende de preflight com `Authorization` (atualmente permitido no `CORS(app, ...)`). **Prod:** baixo risco se usar origem relativa via nginx. **Risco operacional:** se `VITE_CHAT_API_URL` apontar para dominio nao listado em `CORS_ORIGINS`, browser bloqueia. |
| `frontend/src/components/Chatbot.tsx` | `POST /chatbot/chat` (resolve para `${API_BASE_URL}/chatbot/chat`) | POST | `Authorization` via interceptor global do axios (`supabase.auth.getSession()` + fallback `tokenStorage`), `Content-Type: application/json` | Sim (`@token_required`) | Flask `backend/routes/chatbot.py` (`/api/chatbot/chat`) -> `OpenClawService.chat()` -> `openclaw-bridge` -> gateway/LLM | Mesmo perfil de risco do item acima para dev/prod. Como passa pelo client `api`, a chance de inconsistencia de header e menor que no `ChatWidget`. |
| `frontend/src/utils/api.ts` (`chatbotAPI.chat`) | `POST /chatbot/chat` (helper exportado) | POST | `Authorization` via interceptor + `Content-Type: application/json` | Sim | Flask `backend/routes/chatbot.py` (`/api/chatbot/chat`) -> `OpenClawService.chat()` | Sem risco extra alem do padrao CORS global; principal risco e uso futuro com host externo fora de `CORS_ORIGINS`. |
| `frontend/src/utils/api.ts` (`chatbotAPI.getConversation`) | `GET /chatbot/conversations/:conversationId` | GET | `Authorization` via interceptor | Sim | Flask `backend/routes/chatbot.py` (`/api/chatbot/conversations/<id>`) -> `openclaw_service.get_conversation_history()` (bridge `/conversations/<id>`) | Requisicao autenticada cross-origin em dev depende de CORS permitir `Authorization` (permitido hoje). |
| `frontend/src/utils/api.ts` (`chatbotAPI.listConversations`) | `GET /chatbot/conversations` | GET | `Authorization` via interceptor | Sim | Flask `backend/routes/chatbot.py` (`/api/chatbot/conversations`) -> `ChatbotRepository.get_user_conversations()` | Mesmo risco de whitelist de origem em dev/ambientes customizados. |
| `frontend/src/utils/api.ts` (`chatbotAPI.deleteConversation`) | `DELETE /chatbot/conversations/:conversationId` | DELETE | `Authorization` via interceptor | Sim | Flask `backend/routes/chatbot.py` (`/api/chatbot/conversations/<id>`) -> `ChatbotRepository.delete_conversation()` | Metodo `DELETE` em cross-origin exige preflight; backend permite `DELETE` em `methods=[...]`, entao risco baixo enquanto origem estiver autorizada. |
| `frontend/src/utils/api.ts` (`chatbotAPI.health`) | `GET /chatbot/health` | GET | `Authorization` pode ser anexado pelo interceptor, mas endpoint nao exige token | Nao (backend sem `@token_required`) | Flask `backend/routes/chatbot.py` (`/api/chatbot/health`) -> `OpenClawService.health_check()` (bridge `/health`) | Baixo risco; endpoint simples. Em dev continua sujeito a whitelist de origem. |

## Fluxo de destino (cadeia de servicos)

1. Frontend chama endpoints `/api/chatbot/*` (diretamente ou via `API_BASE_URL` + `/api`).
2. Flask (`backend/routes/chatbot.py`) recebe e valida token para rotas protegidas.
3. Para chat e health/historico, Flask chama `OpenClawService` (`backend/services/openclaw_service.py`).
4. `OpenClawService` encaminha para bridge HTTP interno (`OPENCLAW_BRIDGE_URL`, default `http://openclaw-bridge:8089`).
5. Bridge encaminha para gateway/LLM (OpenClaw).
6. Para listagem/delecao de conversas, backend usa `ChatbotRepository` (persistencia de metadados/ownership).

## Pontos de atencao de CORS e seguranca relacionados

- `backend/app.py` nao deixa `*` aberto na pratica: quando `CORS_ORIGINS='*'`, ele faz fallback para localhosts explicitos. Isso protege producao, mas pode quebrar homologacao se dominio nao estiver em `CORS_ORIGINS`.
- `supports_credentials=True` + `Authorization` em headers exige alinhamento fino de origens; qualquer dominio novo precisa entrar no env `CORS_ORIGINS`.
- `ChatWidget` usa token de `localStorage.getItem('auth_token')`, enquanto o client global usa sessao Supabase; isso pode causar falha de autenticacao intermitente (nao e CORS, mas afeta chamadas de chat).
- WebSocket no `ChatWidget` usa `VITE_CHAT_WS_URL` opcional e token na query string (`?token=`). Nao e rota HTTP de `backend/routes/chatbot.py`; hoje o Flask principal nao expoe WS para chatbot. Se ativado em outro servico/dominio, validar politica de origem do WS e evitar log de query string com token.
