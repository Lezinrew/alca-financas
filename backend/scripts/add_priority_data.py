#!/usr/bin/env python3
"""
Script para adicionar dados de prioridades e despesas do usuário lezinrew@gmail.com
"""
import os
import sys
from datetime import datetime
from pymongo import MongoClient
import uuid
from dotenv import load_dotenv

# Adiciona o diretório backend ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Configuração do MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
MONGO_DB = os.getenv('MONGO_DB', 'alca_financas')

# Conecta ao MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
users_collection = db.users
categories_collection = db.categories
transactions_collection = db.transactions
accounts_collection = db.accounts

def get_or_create_category(user_id: str, name: str, category_type: str, color: str, icon: str):
    """Busca ou cria uma categoria"""
    category = categories_collection.find_one({
        'user_id': user_id,
        'name': name,
        'type': category_type
    })
    
    if category:
        return category['_id']
    
    category_data = {
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'name': name,
        'type': category_type,
        'color': color,
        'icon': icon
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
    
    # Cria categorias necessárias
    print("📁 Criando/verificando categorias...")
    
    category_map = {}
    
    # Categorias de despesas
    category_map['Consulta'] = get_or_create_category(user_id, 'Consulta', 'expense', '#96CEB4', 'heart-pulse')
    category_map['Mala Maternidade'] = get_or_create_category(user_id, 'Mala Maternidade', 'expense', '#FF9FF3', 'bag')
    category_map['Carrinho'] = get_or_create_category(user_id, 'Carrinho', 'expense', '#4ECDC4', 'car-front')
    category_map['Rede'] = get_or_create_category(user_id, 'Rede', 'expense', '#45B7D1', 'house')
    category_map['Cortina'] = get_or_create_category(user_id, 'Cortina', 'expense', '#FECA57', 'house')
    category_map['Chuveiro'] = get_or_create_category(user_id, 'Chuveiro', 'expense', '#06b6d4', 'lightning')
    category_map['Sofá'] = get_or_create_category(user_id, 'Sofá', 'expense', '#8b5cf6', 'house')
    category_map['Mesa escrivaninha'] = get_or_create_category(user_id, 'Mesa Escrivaninha', 'expense', '#6366f1', 'tools')
    category_map['Cadeira de Escritório'] = get_or_create_category(user_id, 'Cadeira de Escritório', 'expense', '#6366f1', 'tools')
    category_map['Tinta'] = get_or_create_category(user_id, 'Tinta', 'expense', '#FECA57', 'tools')
    category_map['Aparador'] = get_or_create_category(user_id, 'Aparador', 'expense', '#8b5cf6', 'house')
    category_map['Cabelo Glenda'] = get_or_create_category(user_id, 'Cabelo Glenda', 'expense', '#FF9FF3', 'circle')
    category_map['Ar-Condicionado'] = get_or_create_category(user_id, 'Ar-Condicionado', 'expense', '#06b6d4', 'lightning')
    category_map['Rack'] = get_or_create_category(user_id, 'Rack', 'expense', '#8b5cf6', 'house')
    category_map['Decoração'] = get_or_create_category(user_id, 'Decoração', 'expense', '#FECA57', 'house')
    category_map['Condomínio'] = get_or_create_category(user_id, 'Condomínio', 'expense', '#45B7D1', 'house')
    category_map['Luz'] = get_or_create_category(user_id, 'Luz', 'expense', '#FECA57', 'lightning')
    category_map['Celular/Internet'] = get_or_create_category(user_id, 'Celular/Internet', 'expense', '#6366f1', 'phone')
    category_map['Cartão Leandro'] = get_or_create_category(user_id, 'Cartão Leandro', 'expense', '#8b5cf6', 'credit-card')
    category_map['Cartão Empresa'] = get_or_create_category(user_id, 'Cartão Empresa', 'expense', '#8b5cf6', 'credit-card')
    category_map['Empréstimo Nubank Leandro'] = get_or_create_category(user_id, 'Empréstimo Nubank', 'expense', '#ef4444', 'cash-coin')
    category_map['Cartão Glenda'] = get_or_create_category(user_id, 'Cartão Glenda', 'expense', '#8b5cf6', 'credit-card')
    category_map['Cartão Willbank'] = get_or_create_category(user_id, 'Cartão Willbank', 'expense', '#8b5cf6', 'credit-card')
    category_map['Última parcela Thales'] = get_or_create_category(user_id, 'Parcela Thales', 'expense', '#ef4444', 'cash-coin')
    category_map['Dívida Rochelle'] = get_or_create_category(user_id, 'Dívida Rochelle', 'expense', '#ef4444', 'cash-coin')
    category_map['Prioridades Apto/José'] = get_or_create_category(user_id, 'Prioridades Apto/José', 'expense', '#8b5cf6', 'house')
    category_map['Aluguel/condomínio/IPTU'] = get_or_create_category(user_id, 'Aluguel/Condomínio/IPTU', 'expense', '#45B7D1', 'house')
    category_map['Alimentação'] = get_or_create_category(user_id, 'Alimentação', 'expense', '#FF6B6B', 'basket')
    category_map['Gasolina'] = get_or_create_category(user_id, 'Gasolina', 'expense', '#4ECDC4', 'fuel-pump')
    
    # Categorias de receitas
    category_map['Wagner'] = get_or_create_category(user_id, 'Wagner', 'income', '#10b981', 'currency-dollar')
    category_map['Adonos'] = get_or_create_category(user_id, 'Adonos', 'income', '#10b981', 'currency-dollar')
    category_map['Décimo terceiro'] = get_or_create_category(user_id, 'Décimo Terceiro', 'income', '#10b981', 'currency-dollar')
    category_map['Vale alimentação'] = get_or_create_category(user_id, 'Vale Alimentação', 'income', '#10b981', 'currency-dollar')
    category_map['Marlene'] = get_or_create_category(user_id, 'Marlene', 'income', '#10b981', 'currency-dollar')
    category_map['Outras Entradas'] = get_or_create_category(user_id, 'Outras Entradas', 'income', '#10b981', 'currency-dollar')
    category_map['Venda do carro'] = get_or_create_category(user_id, 'Venda do Carro', 'income', '#10b981', 'car-front')
    
    print(f"✅ {len(category_map)} categorias criadas/verificadas\n")
    
    # Data base para as transações (Nov/Dez 2025)
    from datetime import timedelta
    import random
    
    # Distribui as datas ao longo de Nov/Dez 2025
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 12, 31)
    
    def get_random_date(start, end):
        """Gera uma data aleatória entre start e end"""
        time_between = end - start
        days_between = time_between.days
        random_days = random.randrange(days_between)
        return start + timedelta(days=random_days)
    
    # 1. LISTA DE PRIORIDADES — ALTA PRIORIDADE (detalhadas)
    print("📋 Adicionando prioridades ALTA (detalhadas)...")
    alta_prioridades = [
        ('Consulta', 400.00),
        ('Mala Maternidade', 350.00),
        ('Carrinho', 2800.00),  # Incluído nas prioridades detalhadas, mas não no total consolidado
        ('Rede', 2000.00),
        ('Cortina', 3850.00),
        ('Chuveiro', 700.00),
        ('Sofá', 4990.00),
        ('Mesa escrivaninha', 1200.00),
        ('Cadeira de Escritório', 2500.00),
    ]
    
    alta_transactions = []
    for idx, (item, valor) in enumerate(alta_prioridades):
        # Distribui as datas ao longo de novembro
        transaction_date = start_date + timedelta(days=idx * 3)  # A cada 3 dias
        if transaction_date > datetime(2025, 11, 30):
            transaction_date = datetime(2025, 11, 30)
        
        transaction = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'description': item,
            'amount': valor,
            'type': 'expense',
            'category_id': category_map.get(item, category_map['Prioridades Apto/José']),
            'date': transaction_date,
            'is_recurring': False,
            'status': 'pending',
            'responsible_person': 'Leandro',
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        alta_transactions.append(transaction)
    
    # 2. DESEJOS
    print("📋 Adicionando desejos...")
    desejos = [
        ('Tinta', 2000.00),
        ('Aparador', 3500.00),
        ('Cabelo Glenda', 800.00),
        ('Ar-Condicionado', 3000.00),
        ('Rack', 2000.00),
        ('Decoração', 1000.00),
    ]
    
    desejos_transactions = []
    for idx, (item, valor) in enumerate(desejos):
        # Distribui as datas ao longo de dezembro
        transaction_date = datetime(2025, 12, 1) + timedelta(days=idx * 4)  # A cada 4 dias
        if transaction_date > end_date:
            transaction_date = end_date
        
        transaction = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'description': item,
            'amount': valor,
            'type': 'expense',
            'category_id': category_map.get(item),
            'date': transaction_date,
            'is_recurring': False,
            'status': 'pending',
            'responsible_person': 'Leandro',
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        desejos_transactions.append(transaction)
    
    # 3. DESPESAS PRIORITÁRIAS — Nov/Dez 2025
    # Inclui o total das prioridades altas como um item consolidado
    print("📋 Adicionando despesas prioritárias...")
    despesas = [
        ('Condomínio', 9000.00, 5),  # Dia 5 de novembro
        ('Luz', 300.00, 10),
        ('Celular/Internet', 270.00, 12),
        ('Cartão Leandro', 1300.00, 15),
        ('Cartão Empresa', 500.00, 18),
        ('Empréstimo Nubank Leandro', 219.59, 20),
        ('Cartão Glenda', 550.00, 22),
        ('Cartão Willbank', 100.00, 25),
        ('Última parcela Thales', 501.82, 28),
        ('Dívida Rochelle', 3000.00, 30),
        ('Prioridades Apto/José', 15990.00, 1),  # Dia 1 de novembro
        ('Aluguel/condomínio/IPTU', 3200.00, 7),
        ('Alimentação', 2000.00, 15),  # Distribuído ao longo do mês
        ('Gasolina', 800.00, 20),
    ]
    
    despesas_transactions = []
    for item_data in despesas:
        if len(item_data) == 3:
            item, valor, day = item_data
        else:
            item, valor = item_data
            day = random.randint(1, 30)
        
        # Se for novembro, usa o dia especificado, senão distribui em dezembro
        if day <= 30:
            transaction_date = datetime(2025, 11, day)
        else:
            transaction_date = datetime(2025, 12, day - 30)
        
        transaction = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'description': item,
            'amount': valor,
            'type': 'expense',
            'category_id': category_map.get(item),
            'date': transaction_date,
            'is_recurring': False,
            'status': 'pending',
            'responsible_person': 'Leandro',
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        despesas_transactions.append(transaction)
    
    # 4. OUTRAS ENTRADAS — Nov/Dez 2025
    print("📋 Adicionando entradas...")
    entradas = [
        ('Wagner', 5000.00, 3),  # Dia 3 de novembro
        ('Adonos', 400.00, 8),
        ('Décimo terceiro', 4000.00, 15),  # Meio do mês
        ('Vale alimentação', 590.00, 5),
        ('Marlene', 1700.00, 12),
        ('Outras Entradas', 2268.59, 18),  # Diferença para completar o total de entradas gerais
        ('Venda do carro', 40000.00, 25),  # Final de novembro
    ]
    
    entradas_transactions = []
    for item_data in entradas:
        if len(item_data) == 3:
            item, valor, day = item_data
        else:
            item, valor = item_data
            day = random.randint(1, 30)
        
        # Se for novembro, usa o dia especificado, senão distribui em dezembro
        if day <= 30:
            transaction_date = datetime(2025, 11, day)
        else:
            transaction_date = datetime(2025, 12, day - 30)
        
        transaction = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'description': item,
            'amount': valor,
            'type': 'income',
            'category_id': category_map.get(item),
            'date': transaction_date,
            'is_recurring': False,
            'status': 'pending',
            'responsible_person': 'Leandro',
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        entradas_transactions.append(transaction)
    
    # Insere todas as transações
    all_transactions = alta_transactions + desejos_transactions + despesas_transactions + entradas_transactions
    
    if all_transactions:
        transactions_collection.insert_many(all_transactions)
        print(f"✅ {len(all_transactions)} transações criadas com sucesso!\n")
        
        # Resumo
        # As prioridades altas detalhadas não são somadas nas despesas totais
        # pois já estão consolidadas em "Prioridades Apto/José" nas despesas prioritárias
        # Os desejos também não são incluídos nas despesas prioritárias de Nov/Dez
        total_despesas_prioritarias = sum(t['amount'] for t in despesas_transactions)
        total_desejos = sum(t['amount'] for t in desejos_transactions)
        total_receitas = sum(t['amount'] for t in entradas_transactions)
        saldo = total_receitas - total_despesas_prioritarias
        
        # Cálculo separado das prioridades altas detalhadas
        total_prioridades_detalhadas = sum(t['amount'] for t in alta_transactions)
        
        print("📊 RESUMO:")
        print(f"   Prioridades Alta (detalhadas): {len(alta_transactions)} itens = R$ {total_prioridades_detalhadas:,.2f}")
        print(f"   Desejos: {len(desejos_transactions)} itens = R$ {total_desejos:,.2f}")
        print(f"   Despesas Prioritárias (Nov/Dez): {len(despesas_transactions)} itens = R$ {total_despesas_prioritarias:,.2f}")
        print(f"   Entradas: {len(entradas_transactions)} itens = R$ {total_receitas:,.2f}")
        print(f"\n   Total Despesas Prioritárias: R$ {total_despesas_prioritarias:,.2f}")
        print(f"   Total Receitas: R$ {total_receitas:,.2f}")
        print(f"   Saldo Final (após despesas prioritárias): R$ {saldo:,.2f}")
        print(f"\n   💡 Desejos (não incluídos no cálculo): R$ {total_desejos:,.2f}")
    else:
        print("⚠️  Nenhuma transação para criar")
    
    print("\n✅ Processo concluído!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

