#!/usr/bin/env python3
"""
Script para refatorar categorias do usuário, agrupando categorias muito específicas
em categorias mais genéricas e organizadas
"""
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
MONGO_DB = os.getenv('MONGO_DB', 'alca_financas')

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
users_collection = db.users
categories_collection = db.categories
transactions_collection = db.transactions

# Mapeamento de categorias antigas para novas (mais genéricas)
CATEGORY_MAPPING = {
    # DESPESAS - Agrupamento por tipo
    'expense': {
        # Saúde
        'Consulta': 'Saúde',
        'Saúde': 'Saúde',  # Manter como está
        
        # Casa/Moradia
        'Casa': 'Casa',
        'Aluguel/Condomínio/IPTU': 'Casa',
        'Condomínio': 'Casa',
        'Rede': 'Casa',
        'Cortina': 'Casa',
        'Sofá': 'Casa',
        'Aparador': 'Casa',
        'Rack': 'Casa',
        'Decoração': 'Casa',
        'Tinta': 'Casa',
        'Chuveiro': 'Casa',
        'Ar-Condicionado': 'Casa',
        'Mala Maternidade': 'Casa',
        'Carrinho': 'Casa',  # Carrinho de bebê
        
        # Escritório/Trabalho
        'Mesa Escrivaninha': 'Escritório',
        'Cadeira de Escritório': 'Escritório',
        
        # Utilidades
        'Luz': 'Utilidades',
        'Celular/Internet': 'Utilidades',
        
        # Cartões de Crédito (agrupar todos)
        'Cartão Leandro': 'Cartão de Crédito',
        'Cartão Empresa': 'Cartão de Crédito',
        'Cartão Glenda': 'Cartão de Crédito',
        'Cartão Willbank': 'Cartão de Crédito',
        
        # Empréstimos/Dívidas
        'Empréstimo Nubank': 'Empréstimos',
        'Parcela Thales': 'Empréstimos',
        'Dívida Rochelle': 'Empréstimos',
        
        # Outras categorias específicas
        'Cabelo Glenda': 'Cuidados Pessoais',
        'Prioridades Apto/José': 'Casa',  # Agrupar em Casa
        
        # Manter categorias padrão
        'Alimentação': 'Alimentação',
        'Transporte': 'Transporte',
        'Gasolina': 'Transporte',  # Agrupar gasolina em transporte
    },
    
    # RECEITAS - Agrupar por tipo
    'income': {
        'Wagner': 'Outras Receitas',
        'Adonos': 'Outras Receitas',
        'Marlene': 'Outras Receitas',
        'Outras Entradas': 'Outras Receitas',
        'Décimo Terceiro': 'Salário',
        'Vale Alimentação': 'Salário',
        'Venda do Carro': 'Vendas',
        'Salário': 'Salário',
        'Freelance': 'Freelance',
        'Doações': 'Doações',
    }
}

# Categorias padrão que devem existir
DEFAULT_CATEGORIES = {
    'expense': [
        {'name': 'Alimentação', 'color': '#FF6B6B', 'icon': 'basket'},
        {'name': 'Transporte', 'color': '#4ECDC4', 'icon': 'car-front'},
        {'name': 'Casa', 'color': '#45B7D1', 'icon': 'house'},
        {'name': 'Saúde', 'color': '#96CEB4', 'icon': 'heart-pulse'},
        {'name': 'Utilidades', 'color': '#FECA57', 'icon': 'lightning'},
        {'name': 'Cartão de Crédito', 'color': '#8b5cf6', 'icon': 'credit-card'},
        {'name': 'Empréstimos', 'color': '#ef4444', 'icon': 'cash-coin'},
        {'name': 'Escritório', 'color': '#6366f1', 'icon': 'tools'},
        {'name': 'Cuidados Pessoais', 'color': '#FF9FF3', 'icon': 'circle'},
    ],
    'income': [
        {'name': 'Salário', 'color': '#10b981', 'icon': 'currency-dollar'},
        {'name': 'Freelance', 'color': '#3b82f6', 'icon': 'briefcase'},
        {'name': 'Outras Receitas', 'color': '#10b981', 'icon': 'currency-dollar'},
        {'name': 'Vendas', 'color': '#10b981', 'icon': 'cart'},
        {'name': 'Doações', 'color': '#4ECDC4', 'icon': 'heart'},
    ]
}

def get_or_create_category(user_id: str, name: str, category_type: str, color: str, icon: str):
    """Busca ou cria uma categoria"""
    category = categories_collection.find_one({
        'user_id': user_id,
        'name': name,
        'type': category_type
    })
    
    if category:
        return category['_id']
    
    import uuid
    from datetime import datetime
    
    category_data = {
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'name': name,
        'type': category_type,
        'color': color,
        'icon': icon,
        'created_at': datetime.utcnow()
    }
    categories_collection.insert_one(category_data)
    return category_data['_id']

def main():
    # Busca o usuário
    user = users_collection.find_one({'email': 'lezinrew@gmail.com'})
    
    if not user:
        print("❌ Usuário lezinrew@gmail.com não encontrado!")
        return
    
    user_id = user['_id']
    print(f"✅ Usuário encontrado: {user.get('name')} ({user.get('email')})")
    print(f"   ID: {user_id}\n")
    
    # 1. Criar categorias padrão se não existirem
    print("📁 Criando categorias padrão...")
    new_category_ids = {}
    
    for category_type in ['expense', 'income']:
        for cat_def in DEFAULT_CATEGORIES[category_type]:
            cat_id = get_or_create_category(
                user_id,
                cat_def['name'],
                category_type,
                cat_def['color'],
                cat_def['icon']
            )
            new_category_ids[cat_def['name']] = cat_id
    
    print(f"✅ {len(new_category_ids)} categorias padrão criadas/verificadas\n")
    
    # 2. Buscar todas as categorias antigas
    old_categories = list(categories_collection.find({'user_id': user_id}))
    print(f"📋 Encontradas {len(old_categories)} categorias antigas\n")
    
    # 3. Criar mapeamento de IDs antigos para novos
    old_to_new_id = {}
    categories_to_delete = []
    
    for old_cat in old_categories:
        old_name = old_cat['name']
        old_type = old_cat['type']
        old_id = old_cat['_id']
        
        # Verifica se há mapeamento
        if old_type in CATEGORY_MAPPING and old_name in CATEGORY_MAPPING[old_type]:
            new_name = CATEGORY_MAPPING[old_type][old_name]
            
            # Se a categoria nova já existe, mapeia para ela
            if new_name in new_category_ids:
                new_id = new_category_ids[new_name]
                old_to_new_id[old_id] = new_id
                categories_to_delete.append(old_id)
                print(f"  🔄 '{old_name}' → '{new_name}'")
            else:
                # Se não existe, mantém a categoria antiga mas atualiza
                old_to_new_id[old_id] = old_id
                print(f"  ⚠️  '{old_name}' não tem mapeamento, mantendo")
        else:
            # Categoria não tem mapeamento, verifica se é uma das padrão
            if old_name in new_category_ids:
                # É uma categoria padrão, mantém
                old_to_new_id[old_id] = old_id
                print(f"  ✅ '{old_name}' é categoria padrão, mantendo")
            else:
                # Categoria desconhecida, mantém por enquanto
                old_to_new_id[old_id] = old_id
                print(f"  ⚠️  '{old_name}' não tem mapeamento, mantendo")
    
    print()
    
    # 4. Atualizar transações com novos IDs de categoria
    print("🔄 Atualizando transações...")
    transactions_updated = 0
    
    for old_id, new_id in old_to_new_id.items():
        if old_id != new_id:
            result = transactions_collection.update_many(
                {'user_id': user_id, 'category_id': old_id},
                {'$set': {'category_id': new_id}}
            )
            if result.modified_count > 0:
                transactions_updated += result.modified_count
                print(f"  ✅ {result.modified_count} transações atualizadas de '{old_id}' para '{new_id}'")
    
    print(f"\n✅ Total de {transactions_updated} transações atualizadas\n")
    
    # 5. Deletar categorias antigas que foram agrupadas
    print("🗑️  Removendo categorias duplicadas...")
    deleted_count = 0
    
    for cat_id in categories_to_delete:
        # Verifica se ainda há transações usando essa categoria
        count = transactions_collection.count_documents({'user_id': user_id, 'category_id': cat_id})
        if count == 0:
            categories_collection.delete_one({'_id': cat_id})
            deleted_count += 1
            print(f"  ✅ Categoria '{cat_id}' removida")
        else:
            print(f"  ⚠️  Categoria '{cat_id}' ainda tem {count} transações, não removida")
    
    print(f"\n✅ {deleted_count} categorias removidas\n")
    
    # 6. Resumo final
    final_categories = list(categories_collection.find({'user_id': user_id}).sort('type', 1))
    expense_count = len([c for c in final_categories if c['type'] == 'expense'])
    income_count = len([c for c in final_categories if c['type'] == 'income'])
    
    print("📊 RESUMO FINAL:")
    print(f"   Categorias de Despesa: {expense_count}")
    print(f"   Categorias de Receita: {income_count}")
    print(f"   Total: {len(final_categories)} categorias")
    print("\n✅ Refatoração concluída!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

