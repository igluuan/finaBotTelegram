def parse_float(text: str) -> float:
    try:
        valor = float(text.strip().replace(',', '.'))
        return valor
    except ValueError:
        return None

def validar_dia(text: str) -> int:
    try:
        dia = int(text.strip())
        if 1 <= dia <= 31:
            return dia
    except ValueError:
        pass
    return None

def validar_cartao(text: str) -> str:
    cleaned = text.strip()
    if cleaned.isdigit() and len(cleaned) == 4:
        return cleaned
    return None
