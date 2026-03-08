from typing import Union
from datetime import datetime
from utils.exceptions import ValidationException

def parse_date_value(value: Union[str, datetime, None]) -> datetime:
    """
    Converte valor de data (string em vários formatos ou datetime) para datetime.
    Levanta ValidationException se a data for inválida ou vazia.

    Formatos aceitos em string:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - ISO 8601 (YYYY-MM-DDTHH:MM:SS...)
    """
    if not value:
        raise ValidationException("Data não fornecida ou vazia.")
    
    if isinstance(value, datetime):
        return value
        
    s = str(value).strip()
    if not s:
        raise ValidationException("Data fornecida é inválida ou vazia.")
        
    # Tenta YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        pass
        
    # Tenta DD/MM/YYYY
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        pass
        
    # Tenta formato ISO
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        pass

    raise ValidationException(f"Formato de data não reconhecido: '{s}'. Use YYYY-MM-DD ou DD/MM/YYYY.")
