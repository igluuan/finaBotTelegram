import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Any

from ..database import crud
from .ai_service import generate_content

logger = logging.getLogger(__name__)

CATEGORIAS_OPCOES = {
    "Alimentação": "alimentacao",
    "Transporte": "transporte",
    "Mercado": "mercado",
    "Moradia": "moradia",
    "Lazer": "lazer",
    "Saúde": "saude",
    "Educação": "educacao",
    "Assinaturas": "assinaturas",
    "Outros": "outros",
}

def get_categoria_key(nome_display: str) -> Optional[str]:
    """Retorna a chave da categoria baseada no nome de exibição."""
    return CATEGORIAS_OPCOES.get(nome_display)

def verificar_orcamento(user_id: int, categoria: str, valor: float) -> Dict[str, Any]:
    """
    Verifica o status do orçamento para uma categoria após um novo gasto.
    Retorna um dicionário com informações sobre o orçamento.
    """
    hoje = datetime.now()
    gastos_cat = crud.get_gastos_por_categoria(user_id, hoje.month, hoje.year)
    total_cat = next((item['total'] for item in gastos_cat if item['categoria'] == categoria), 0.0)
    
    orcamento = crud.get_orcamento_status(user_id, hoje.month, hoje.year)
    orc_cat = next((item for item in orcamento if item['categoria'] == categoria), None)
    
    resultado = {
        "total_acumulado": total_cat,
        "limite": 0.0,
        "percentual": 0.0,
        "alerta": False,
        "mensagem_alerta": ""
    }
    
    if orc_cat and orc_cat['limite'] > 0:
        resultado["limite"] = orc_cat['limite']
        resultado["percentual"] = orc_cat['percentual']
        
        if resultado["percentual"] > 80:
            resultado["alerta"] = True
            resultado["mensagem_alerta"] = "⚠️ *Atenção:* Você atingiu 80% do orçamento!"
            
    return resultado

async def verificar_anomalia(user_id: int, categoria: str, valor: float, descricao: str, data_gasto: Optional[date] = None) -> Dict[str, Any]:
    """
    Verifica se o gasto é uma anomalia baseada no histórico do usuário.
    """
    historico = crud.get_historico_categoria(user_id, categoria, dias=30)
    if not historico:
        return {"incomum": False}

    try:
        hist_str = json.dumps(
            [
                {
                    "data": g.data.isoformat(),
                    "valor": g.valor,
                    "descricao": g.descricao,
                }
                for g in historico
            ],
            ensure_ascii=False
        )
        
        hoje = date.today()
        data_novo = data_gasto or hoje
        novo = json.dumps(
            {
                "data": data_novo.isoformat(),
                "valor": valor,
                "descricao": descricao,
            },
            ensure_ascii=False
        )
        
        prompt = f"""
SYSTEM:
Dado o histórico abaixo, avalie se o novo gasto é incomum para o usuário.
Retorne APENAS JSON:

{{
  "incomum": true,
  "motivo": "Valor 3x acima da média de R$ 45 em restaurantes",
  "percentual_acima": 200
}}

USER:
Histórico: {hist_str}
Novo gasto: {novo}
"""
        response_text = await generate_content(prompt)
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
        
    except (json.JSONDecodeError, TypeError, Exception) as e:
        logger.warning(f"Falha ao verificar anomalia: {e}", extra={"user_id": user_id, "categoria": categoria})
        return {"incomum": False}
