"""
Categorizador de transações baseado em regras por tenant (merchant_category_aliases).

Princípios:
1. Matching pela maior palavra-chave primeiro (mais específica vence).
2. Boundary regex `(?<![0-9A-Z])` para não casar no meio de palavras.
3. Sem correspondência -> "Não classificado" (nunca adivinhação).
"""
import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class AliasCategorizer:
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        """
        rules: Lista de dicionários contendo:
        {
            'keyword': str (ou 'merchant_name' / 'alias'),
            'category_name': str,
            'subcategory': Optional[str],
            'responsible_person': Optional[str]
        }
        """
        self.rules = []
        if rules:
            self.load_rules(rules)

    def load_rules(self, rules: List[Dict[str, Any]]) -> None:
        """Carrega e ordena as regras por maior comprimento da palavra-chave."""
        processed = []
        for r in rules:
            keyword = r.get('keyword') or r.get('merchant_name') or r.get('alias') or ''
            keyword_clean = _strip_accents(keyword).strip().upper()
            if not keyword_clean:
                continue
                
            cat_name = r.get('category_name') or r.get('category') or 'Não classificado'
            subcat = r.get('subcategory') or r.get('subcat')
            resp = r.get('responsible_person') or r.get('default_responsible_person')
            
            # Compila o regex com boundary
            pattern = re.compile(
                rf'(?<![0-9A-Z]){re.escape(keyword_clean)}(?![0-9A-Z])',
                re.IGNORECASE
            )
            
            processed.append({
                'keyword': keyword_clean,
                'length': len(keyword_clean),
                'pattern': pattern,
                'category_name': cat_name,
                'subcategory': subcat,
                'responsible_person': resp
            })
            
        # Ordena do maior para o menor comprimento (mais específico vence)
        self.rules = sorted(processed, key=lambda x: x['length'], reverse=True)

    def categorize(self, description: str) -> Dict[str, Any]:
        """
        Categoriza a descrição da transação.
        Retorna:
        {
            'category_name': str,
            'subcategory': Optional[str],
            'responsible_person': Optional[str],
            'matched_rule': Optional[str],
            'is_classified': bool
        }
        """
        desc_norm = _strip_accents(description or '').strip().upper()
        
        for rule in self.rules:
            if rule['pattern'].search(desc_norm):
                return {
                    'category_name': rule['category_name'],
                    'subcategory': rule['subcategory'],
                    'responsible_person': rule['responsible_person'],
                    'matched_rule': rule['keyword'],
                    'is_classified': True
                }
                
        return {
            'category_name': 'Não classificado',
            'subcategory': None,
            'responsible_person': None,
            'matched_rule': None,
            'is_classified': False
        }
