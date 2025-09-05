### Prompt para Refatoração do Backend (Mobills Pro)

Use este prompt para orientar refatorações futuras e manter a estrutura modular do backend consistente com o estado atual do projeto.

```
Refatore o backend da API do projeto Mobills Pro seguindo estas diretrizes e padrões já adotados no código atual.

Objetivo
- Manter `backend/app.py` como ponto de entrada: configura CORS, OAuth, conexão MongoDB e registra Blueprints.
- Rotas em `routes/` via Blueprints, com validação leve e delegação de negócio para `services/`.
- Lógicas de negócio, conversões, parcelamentos/recorrências e agregações do MongoDB em `services/`.
- Utilitários de autenticação em `utils/auth_utils.py` (hash, check, JWT, require_auth).

Padrões de Prefixo e Registro de Blueprints
- `auth`: Blueprint SEM `url_prefix`; todas as rotas começam com `/auth/...` no arquivo. Registrar no `app.py` com `url_prefix='/api'` para resultar em `/api/auth/...`.
- `categories`: Blueprint COM `url_prefix='/api/categories'`.
- `transactions`: Blueprint COM `url_prefix='/api/transactions'`.
- `accounts`: Blueprint COM `url_prefix='/api/accounts'`.
- `dashboard`: Blueprint COM `url_prefix='/api'` (rotas começam com `/dashboard`).
- `reports`: Blueprint COM `url_prefix='/api/reports'`.

Estado atual (mantê-lo como referência)
- OAuth: registrado logo após CORS em `app.py` e fora de blocos condicionais.
- Coleções MongoDB acessadas via `current_app.config['USERS' | 'CATEGORIES' | 'TRANSACTIONS' | 'ACCOUNTS']` dentro das rotas.
- Blueprints já existentes: `auth`, `categories`, `transactions`, `accounts`, `dashboard`, `reports`.
- Serviços já existentes: `user_service`, `category_service`, `transaction_service`, `account_service`, `report_service`.

Tarefas de Refatoração por Módulo (modelo)
1) Transações (`/api/transactions`)
   - Rotas em `routes/transactions.py`.
   - Lógicas (filtro, validações, parcelamento/recorrência, atualização de saldo) em `services/transaction_service.py`.
   - As rotas acessam coleções via `current_app.config` e delegam ao serviço.

2) Contas (`/api/accounts`)
   - Rotas em `routes/accounts.py`.
   - Lógicas de CRUD e validações em `services/account_service.py`.

3) Dashboard e Relatórios (`/api/dashboard` e `/api/reports`)
   - Rotas em `routes/dashboard.py` e `routes/reports.py`.
   - Agregações do MongoDB e cálculos em `services/report_service.py`.

4) Autenticação (`/api/auth/...`)
   - Rotas em `routes/auth.py` (todas começam com `/auth/...`).
   - Registrar o Blueprint com `url_prefix='/api'` em `app.py`.
   - `redirect_uri` do Google: `.../api/auth/google/callback`.

Checklist ao concluir cada módulo
- [ ] Rotas migradas para `routes/<modulo>.py` usando Blueprint.
- [ ] Lógica de negócio movida para `services/<modulo>_service.py`.
- [ ] Importações ajustadas (usar `current_app.config` para coleções e `utils/auth_utils` quando necessário).
- [ ] `app.py` atualizado (se houver novo Blueprint) e registrado com o prefixo correto.
- [ ] Endpoint `/api/health` permanece funcional.

Exemplo de Blueprint (padrão)
```python
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth

bp = Blueprint('example', __name__, url_prefix='/api/example')

@bp.route('', methods=['GET'])
@require_auth
def list_items():
    collection = current_app.config['DB'].example
    items = list(collection.find({'user_id': request.user_id}))
    for it in items:
        it['id'] = it.pop('_id', None)
    return jsonify(items)
```

Exemplo de Serviço (padrão)
```python
from typing import Dict, Any, List

def list_entities(collection, user_id: str) -> List[Dict[str, Any]]:
    data = list(collection.find({'user_id': user_id}))
    for d in data:
        if '_id' in d:
            d['id'] = d['_id']
            d.pop('_id', None)
    return data
```

Notas
- Siga a ordem dos imports (padrão/terceiros/projeto) e padronize docstrings curtas quando fizer ajustes de lint.
- Não duplicar lógicas entre rotas e serviços; rotas só orquestram e validam superficialmente.
```


