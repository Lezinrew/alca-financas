# Serviço FastAPI legado (`services/chatbot`)

**Estado:** legado / referência — **não** é o runtime oficial do produto.

**Runtime oficial:** Flask em `backend/routes/chatbot.py`, exposto em **`/api/chatbot/*`** (HTTP). O frontend deve usar `chatbotAPI` em `frontend/src/utils/api.ts` e/ou `ChatWidget` com base `.../api/chatbot`.

Este diretório (`FastAPI`, `/api/chat`, `/api/chat/ws`) mantém-se no repositório até **arquivoção explícita** após validação final (ver `TODO.md` / `EXECUTION_RUNBOOK.md` bloco P0-B). Não adicionar novas integrações aqui.
