"""
Serviço para detectar e criar categorias automaticamente baseado em palavras-chave
"""
import re
from typing import Dict, Any, Optional, Tuple

# Mapeamento de palavras-chave para categorias
CATEGORY_KEYWORDS = {
    'Alimentação': {
        'keywords': [
            'restaurante', 'lanchonete', 'padaria', 'supermercado', 'mercado', 'açougue',
            'peixaria', 'hortifruti', 'delivery', 'ifood', 'rappi', 'uber eats', 'mcdonalds',
            'burger king', 'subway', 'pizza', 'pizzaria', 'café', 'cafeteria', 'starbucks',
            'bebida', 'bebidas', 'bar', 'boteco', 'cervejaria', 'churrascaria', 'sorveteria',
            'doceria', 'confeitaria', 'fast food', 'comida', 'alimento', 'alimentação',
            'marukame', 'coco bambu', 'dona conce', 'pizza pazza', 'mi garba', 'estripulia',
            'tradição da roca', 'patio', 'restaurante', 'rest', 'lanche', 'lanches'
        ],
        'color': '#FF6B6B',
        'icon': 'basket'
    },
    'Transporte': {
        'keywords': [
            'uber', 'taxi', '99', 'cabify', 'posto', 'combustível', 'gasolina', 'etanol',
            'diesel', 'estacionamento', 'parking', 'pedágio', 'pedagio', 'metro', 'metrô',
            'ônibus', 'onibus', 'bilhete', 'passagem', 'transporte', 'viagem', 'viagens',
            'aéreo', 'aereo', 'aviao', 'avião', 'hotel', 'hospedagem', 'aluguel de carro',
            'zeppelin', 'tereza cristina', 'quick', 'lagoa santa', 'auto bitts', 'direcao',
            'direção', 'auto', 'carro', 'moto', 'bicicleta', 'bike'
        ],
        'color': '#4ECDC4',
        'icon': 'car-front'
    },
    'Saúde': {
        'keywords': [
            'farmacia', 'farmácia', 'drogaria', 'drogaria araujo', 'raia', 'pacheco',
            'medicamento', 'remédio', 'remedio', 'consulta', 'médico', 'medico', 'dentista',
            'clínica', 'clinica', 'hospital', 'exame', 'laboratório', 'laboratorio',
            'plano de saúde', 'unimed', 'amil', 'sulamerica', 'saude', 'saúde'
        ],
        'color': '#96CEB4',
        'icon': 'heart-pulse'
    },
    'Casa': {
        'keywords': [
            'luz', 'energia', 'cemig', 'copel', 'água', 'agua', 'sabesp', 'sanepar',
            'gás', 'gas', 'copa energia', 'internet', 'net', 'vivo', 'claro', 'oi', 'tim',
            'telefone', 'celular', 'aluguel', 'condomínio', 'condominio', 'iptu', 'iptu',
            'reforma', 'construção', 'construcao', 'material de construção', 'decoração',
            'decoracao', 'móveis', 'moveis', 'eletrodomésticos', 'eletrodomesticos',
            'limpeza', 'produtos de limpeza', 'supermercado 2b', 'supermercado e padaria'
        ],
        'color': '#45B7D1',
        'icon': 'house'
    },
    'Educação': {
        'keywords': [
            'escola', 'faculdade', 'universidade', 'curso', 'cursos', 'aula', 'aulas',
            'livro', 'livros', 'material escolar', 'mensalidade', 'matrícula', 'matricula',
            'ensino', 'educação', 'educacao', 'apostila', 'apostilas'
        ],
        'color': '#9B59B6',
        'icon': 'book'
    },
    'Lazer': {
        'keywords': [
            'cinema', 'teatro', 'show', 'shows', 'festival', 'festivais', 'ingresso',
            'ingressos', 'parque', 'parques', 'diversão', 'diversao', 'fator diversoes',
            'jogo', 'jogos', 'videogame', 'playstation', 'xbox', 'nintendo', 'streaming',
            'netflix', 'spotify', 'amazon prime', 'disney', 'hbo', 'youtube premium',
            'diamond mall', 'shopping', 'loja', 'lojas', 'compras', 'compra'
        ],
        'color': '#F39C12',
        'icon': 'film'
    },
    'Vestuário': {
        'keywords': [
            'roupa', 'roupas', 'vestuário', 'vestuario', 'calçado', 'calcado', 'sapato',
            'sapatos', 'camisa', 'camisas', 'calça', 'calcas', 'moda', 'fashion',
            'boutique', 'loja de roupas', 'zara', 'h&m', 'renner', 'c&a', 'riachuelo',
            'slo silva lobo', 'borelli', 'lindt'
        ],
        'color': '#E74C3C',
        'icon': 'shirt'
    },
    'Serviços': {
        'keywords': [
            'banco', 'tarifa', 'tarifas', 'anuidade', 'anuidades', 'taxa', 'taxas',
            'serviço', 'servicos', 'manutenção', 'manutencao', 'reparo', 'reparos',
            'conserto', 'consertos', 'tabelionato', 'cartório', 'cartorio', 'documento',
            'documentos', 'cpf', 'rg', 'certidão', 'certidao'
        ],
        'color': '#95A5A6',
        'icon': 'tools'
    },
    'Doações': {
        'keywords': [
            'doação', 'doacoes', 'doação', 'doar', 'caridade', 'ong', 'ong\'s',
            'comunidade', 'igreja', 'templo', 'dízimo', 'dizimo', 'oferta', 'ofertas',
            'comunidade crista luz', 'comun crist luz nacoes'
        ],
        'color': '#E67E22',
        'icon': 'heart'
    },
    'Pessoal': {
        'keywords': [
            'salão', 'salao', 'cabeleireiro', 'cabeleireira', 'barbeiro', 'barbeiro',
            'estética', 'estetica', 'spa', 'massagem', 'unha', 'unhas', 'manicure',
            'pedicure', 'cosmético', 'cosmetico', 'perfume', 'perfumes', 'maquiagem'
        ],
        'color': '#3498DB',
        'icon': 'person'
    },
    'Pets': {
        'keywords': [
            'pet', 'pets', 'cachorro', 'cachorros', 'gato', 'gatos', 'veterinário',
            'veterinario', 'ração', 'racao', 'pet shop', 'petshop', 'animal', 'animais'
        ],
        'color': '#1ABC9C',
        'icon': 'paw'
    },
    'Outros': {
        'keywords': [],
        'color': '#6C757D',
        'icon': 'circle'
    }
}


def detect_category_from_description(description: str) -> Optional[Tuple[str, str, str]]:
    """
    Detecta a categoria baseado na descrição da transação.
    Retorna: (nome_categoria, cor, ícone) ou None se não conseguir detectar
    """
    if not description:
        return None
    
    description_lower = description.lower()
    
    # Remove caracteres especiais e normaliza
    description_clean = re.sub(r'[^\w\s]', ' ', description_lower)
    words = description_clean.split()
    
    # Conta matches por categoria
    category_scores = {}
    
    for category_name, category_data in CATEGORY_KEYWORDS.items():
        if category_name == 'Outros':
            continue
            
        score = 0
        keywords = category_data['keywords']
        
        for keyword in keywords:
            # Busca palavra completa ou parcial
            if keyword in description_lower:
                # Se a palavra tem mais de 4 caracteres, dá mais peso
                if len(keyword) > 4:
                    score += 2
                else:
                    score += 1
        
        if score > 0:
            category_scores[category_name] = {
                'score': score,
                'color': category_data['color'],
                'icon': category_data['icon']
            }
    
    # Retorna a categoria com maior score
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1]['score'])
        return (best_category[0], best_category[1]['color'], best_category[1]['icon'])
    
    # Se não encontrou nenhuma, retorna "Outros"
    return ('Outros', CATEGORY_KEYWORDS['Outros']['color'], CATEGORY_KEYWORDS['Outros']['icon'])


def get_or_create_category(
    categories_collection,
    user_id: str,
    category_name: str,
    category_type: str,
    color: Optional[str] = None,
    icon: Optional[str] = None
) -> str:
    """
    Busca uma categoria pelo nome ou cria uma nova se não existir.
    Retorna o ID da categoria.
    """
    # Busca categoria existente
    existing_category = categories_collection.find_one({
        'user_id': user_id,
        'name': category_name,
        'type': category_type
    })
    
    if existing_category:
        return existing_category['_id']
    
    # Cria nova categoria
    from services.category_service import create_category
    
    category_data = {
        'name': category_name,
        'type': category_type,
        'color': color or '#6C757D',
        'icon': icon or 'circle'
    }
    
    new_category = create_category(categories_collection, user_id, category_data)
    return new_category['id']

