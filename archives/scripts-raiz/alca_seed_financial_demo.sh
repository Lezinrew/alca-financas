#!/usr/bin/env bash
set -eo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
MONGO_DB="${MONGO_DB:-alca_financas}"
USER_EMAIL="${USER_EMAIL:-demo@alca.fin}"

cd "$BACKEND_DIR"
source .venv/bin/activate 2>/dev/null || { python3 -m venv .venv && source .venv/bin/activate; }
python -m pip install --upgrade pip >/dev/null
pip install pymongo >/dev/null

python - <<'PY'
import os, uuid
from datetime import datetime
from pymongo import MongoClient

MONGO_URI=os.getenv('MONGO_URI','mongodb://localhost:27017')
MONGO_DB=os.getenv('MONGO_DB','alca_financas')
USER_EMAIL=os.getenv('USER_EMAIL','demo@alca.fin')

client=MongoClient(MONGO_URI)
db=client[MONGO_DB]
user=db.users.find_one({'email': USER_EMAIL})
if not user:
    raise SystemExit(f"Usuário {USER_EMAIL} não encontrado. Execute o seed do usuário demo antes.")
user_id=str(user['_id'])

# Define categorias (slug->definition)
categories_def=[
    ("salario",            {"name":"Salário",            "type":"income",  "color":"#22c55e", "icon":"currency-dollar"}),
    ("freelance",          {"name":"Freelance",          "type":"income",  "color":"#3b82f6", "icon":"briefcase"}),
    ("investimentos",      {"name":"Investimentos",      "type":"income",  "color":"#10b981", "icon":"graph-up-arrow"}),
    ("renda-extra",        {"name":"Renda Extra",        "type":"income",  "color":"#f59e0b", "icon":"lightning"}),
    ("doacao-recorrente",  {"name":"Doação Recorrente",  "type":"income",  "color":"#e11d48", "icon":"heart"}),
    ("moradia",            {"name":"Moradia",            "type":"expense", "color":"#ef4444", "icon":"house"}),
    ("alimentacao",        {"name":"Alimentação",        "type":"expense", "color":"#f97316", "icon":"basket"}),
    ("transporte",         {"name":"Transporte",         "type":"expense", "color":"#8b5cf6", "icon":"car-front"}),
    ("saude",              {"name":"Saúde",              "type":"expense", "color":"#dc2626", "icon":"heart-pulse"}),
    ("educacao",           {"name":"Educação",           "type":"expense", "color":"#059669", "icon":"book"}),
    ("utilidades",         {"name":"Utilidades",         "type":"expense", "color":"#eab308", "icon":"lightning"}),
    ("assinaturas",        {"name":"Assinaturas",        "type":"expense", "color":"#6366f1", "icon":"credit-card"}),
    ("vestuario",          {"name":"Vestuário",          "type":"expense", "color":"#ec4899", "icon":"bag"}),
    ("lazer",              {"name":"Lazer",              "type":"expense", "color":"#06b6d4", "icon":"controller"}),
    ("cuidados-pessoais",  {"name":"Cuidados Pessoais",  "type":"expense", "color":"#f472b6", "icon":"emoji-smile"}),
    ("impostos",           {"name":"Impostos",           "type":"expense", "color":"#374151", "icon":"bank"}),
    ("emprestimos",        {"name":"Empréstimos",        "type":"expense", "color":"#991b1b", "icon":"cash-coin"}),
    ("investimentos-gastos", {"name":"Investimentos (Gastos)","type":"expense","color":"#065f46","icon":"piggy-bank"}),
    ("pets",               {"name":"Pets",               "type":"expense", "color":"#92400e", "icon":"paw"}),
    ("doacoes",            {"name":"Doações",            "type":"expense", "color":"#be185d", "icon":"heart"}),
    ("emergencia",         {"name":"Emergência",         "type":"expense", "color":"#b91c1c", "icon":"exclamation-triangle"}),
]

slug_to_id={}
for slug, data in categories_def:
    existing=db.categories.find_one({'user_id': user_id, 'name': data['name'], 'type': data['type']})
    if existing:
        slug_to_id[slug]=existing['_id']
        continue
    doc={
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'name': data['name'],
        'type': data['type'],
        'color': data['color'],
        'icon': data['icon'],
        'created_at': datetime.utcnow(),
    }
    db.categories.insert_one(doc)
    slug_to_id[slug]=doc['_id']

# Transações (amostra)
raw_tx=[
    { "cat":"freelance", "type":"income",  "desc":"PDCase",                "amount":5785.49, "date":"2025-05-01" },
    { "cat":"doacao-recorrente","type":"income","desc":"Marlene (mae)",    "amount":1700.00, "date":"2025-05-05" },
    { "cat":"impostos", "type":"expense", "desc":"IPTU 2023 e 2024",       "amount":3782.90, "date":"2025-05-01" },
    { "cat":"moradia",  "type":"expense", "desc":"Condomínio (fev a mai)", "amount":3756.00, "date":"2025-05-01" },
    { "cat":"lazer",    "type":"expense", "desc":"Clube dos Oficiais",     "amount":1332.00, "date":"2025-05-01" },
    { "cat":"utilidades","type":"expense","desc":"Conta de Luz (maio)",    "amount":179.04,  "date":"2025-05-01" },
    { "cat":"utilidades","type":"expense","desc":"Gás",                    "amount":45.95,   "date":"2025-05-01" },
    { "cat":"transporte","type":"expense","desc":"Gasolina",               "amount":196.19,  "date":"2025-05-01" },
    { "cat":"assinaturas","type":"expense","desc":"Microsoft 365",         "amount":51.00,   "date":"2025-05-01" },
    { "cat":"assinaturas","type":"expense","desc":"Google One",            "amount":96.99,   "date":"2025-05-01" },
    { "cat":"assinaturas","type":"expense","desc":"ChatGPT Plus",          "amount":99.00,   "date":"2025-05-01" },
    { "cat":"assinaturas","type":"expense","desc":"Canva Pro",             "amount":36.50,   "date":"2025-05-01" },
    { "cat":"saude",     "type":"expense","desc":"Venvanse",               "amount":202.00,  "date":"2025-05-01" },
    { "cat":"saude",     "type":"expense","desc":"Pediatra Duda",          "amount":500.00,  "date":"2025-05-01" },
    { "cat":"alimentacao","type":"expense","desc":"Bolo revelação",        "amount":130.00,  "date":"2025-05-01" },
    { "cat":"alimentacao","type":"expense","desc":"McDonald\"s",         "amount":95.70,   "date":"2025-05-01" },
    { "cat":"vestuario", "type":"expense","desc":"Capinha celular Glenda", "amount":40.00,   "date":"2025-05-01" },
    { "cat":"cuidados-pessoais","type":"expense","desc":"Corte cabelo Glenda","amount":230.00,"date":"2025-05-01" },
    { "cat":"cuidados-pessoais","type":"expense","desc":"Corte cabelo Leandro","amount":130.00,"date":"2025-05-01" },
    { "cat":"utilidades","type":"expense","desc":"TIM Celular",            "amount":350.99,  "date":"2025-05-01" },
    { "cat":"utilidades","type":"expense","desc":"Internet TIM",           "amount":109.99,  "date":"2025-05-01" },
    { "cat":"emprestimos","type":"expense","desc":"Empréstimo Nu",         "amount":204.98,  "date":"2025-05-01" },
    { "cat":"emprestimos","type":"expense","desc":"Patty",                 "amount":200.00,  "date":"2025-05-01" },
    { "cat":"emprestimos","type":"expense","desc":"Alan",                  "amount":312.50,  "date":"2025-05-01" },
]

insert_docs=[]
for t in raw_tx:
    cat_id=slug_to_id.get(t['cat'])
    if not cat_id:
        continue
    dt=datetime.strptime(t['date'], '%Y-%m-%d')
    insert_docs.append({
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'description': t['desc'],
        'amount': float(t['amount']),
        'type': t['type'],
        'category_id': cat_id,
        'date': dt,
        'is_recurring': False,
        'installment_info': None,
        'created_at': datetime.utcnow(),
    })

if insert_docs:
    db.transactions.insert_many(insert_docs)
print(f"Categorias ativas: {len(slug_to_id)}; Transações inseridas: {len(insert_docs)}")
PY

echo "Seed financeiro concluído."

