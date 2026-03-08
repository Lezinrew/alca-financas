"""
Utilitários para valores monetários.

- Parsing consistente de strings/numbers (pt-BR: 1.000,50 ou 1000,50; en: 1000.50).
- Uso em serviços que recebem amount, balance, limit, initial_balance, etc.
"""
from typing import Union
from utils.exceptions import ValidationException

def parse_money_value(value: Union[str, int, float, None]) -> float:
    """
    Converte valor monetário (string ou número) para float.

    Aceita:
    - Número: int/float retornado como float.
    - String pt-BR: "1.000,50", "68.099", "100,00", "R$ 1.234,56".
    - String en: "1000.50", "1000".
    
    Levanta ValidationException para valores vazios, zerados, negativos ou inválidos.
    """
    if value is None or value == "":
        raise ValidationException("Valor financeiro não fornecido ou vazio.")
    
    if isinstance(value, (int, float)):
        val = float(value)
        if val <= 0:
            raise ValidationException("Valor da transação deve ser maior que zero.")
        return val
        
    s = str(value).strip().replace("R$", "").replace(" ", "")
    if not s:
        raise ValidationException("Valor financeiro não fornecido ou vazio.")
    # pt-BR: vírgula = decimal, ponto = milhares
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # Sem vírgula: pode ser "1.000" (mil pt-BR) ou "1.5" (decimal en)
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            # "1.000" → milhares pt-BR
            s = s.replace(".", "")
        # senão mantém como está (decimal en: "1.5" → 1.5)
    try:
        val = float(s)
        if val <= 0:
            raise ValidationException("Valor da transação deve ser maior que zero.")
        return val
    except ValueError:
        raise ValidationException(f"Formato de valor financeiro não reconhecido: '{value}'.")
