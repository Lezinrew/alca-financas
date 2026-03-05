# Corrigir erro de login: 502 Bad Gateway e CORS

Quando o login em **https://alcahub.cloud** mostra "Não foi possível conectar" e o console exibe **502 (Bad Gateway)** e **CORS (No 'Access-Control-Allow-Origin' header)**, siga os passos abaixo.

---

## 1. Corrigir o 502 (Bad Gateway)

O 502 indica que o **proxy/reverso (Nginx, load balancer, etc.)** não está conseguindo falar com o **backend** que atende a API (`api.alcahub.cloud`).

**No servidor de produção:**

1. **Confirmar se o backend está rodando**
   - Ex.: processo Python/Gunicorn escutando na porta configurada (ex.: 8001).
   - Se usar Docker/systemd, verificar com `docker ps` / `systemctl status` e logs.

2. **Confirmar como o proxy encaminha para o backend**
   - Nginx: `proxy_pass` apontando para o host/porta corretos (ex.: `http://127.0.0.1:8001` ou `http://backend:8001`).
   - Se o backend estiver em outro host/porta, ajustar `proxy_pass` e reiniciar o Nginx.

3. **Ver logs do proxy e do backend**
   - Nginx: `error_log` (ex.: `/var/log/nginx/error.log`).
   - Backend: logs da aplicação (Gunicorn/Flask).
   - Erros comuns: backend parado, porta errada, timeout, conexão recusada.

4. **Reiniciar o backend e o proxy** após qualquer alteração.

Enquanto o 502 persistir, o navegador pode mostrar também CORS, porque a resposta de erro (502) muitas vezes vem do proxy e não inclui os headers CORS do Flask.

---

## 2. Corrigir o CORS em produção

O front está em **https://alcahub.cloud** e a API em **https://api.alcahub.cloud**. O backend precisa autorizar essa origem.

**No servidor onde o backend roda**, defina a variável de ambiente **CORS_ORIGINS** com a URL do front (e variantes, se precisar):

```bash
# Exemplo: só o domínio principal
export CORS_ORIGINS="https://alcahub.cloud"

# Ou com www e sem www
export CORS_ORIGINS="https://alcahub.cloud,https://www.alcahub.cloud"
```

- Se usar **.env**: adicione no arquivo `.env` do backend:
  ```env
  CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud
  ```
- Se usar **Docker/Compose**: defina no `environment` do serviço do backend.
- Se usar **GitHub Actions / deploy**: configure `CORS_ORIGINS` nos secrets ou variáveis do ambiente de produção.

Depois **reinicie o backend** para carregar a nova variável.

**Importante:** não use `*` em produção com `supports_credentials=True`; use sempre a lista explícita de origens (ex.: `https://alcahub.cloud`).

---

## 3. Ordem recomendada

1. Resolver o **502** (backend no ar e proxy apontando para ele).
2. Configurar **CORS_ORIGINS** com `https://alcahub.cloud` (e www se usar) e reiniciar o backend.
3. Testar o login de novo em **https://alcahub.cloud**.

Se o 502 sumir e o CORS estiver configurado, o erro de CORS no console deve desaparecer e o login deve funcionar.
