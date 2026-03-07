import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.budget_repository import BudgetRepository
from finbot.services.ai_service import generate_content

logger = logging.getLogger(__name__)

CATEGORY_OPTIONS = {
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

def get_category_key(display_name: str) -> Optional[str]:
    """Returns the category key based on display name."""
    return CATEGORY_OPTIONS.get(display_name)

def check_budget(user_id: int, category: str, amount: float) -> Dict[str, Any]:
    """
    Checks budget status for a category after a new expense.
    Returns a dictionary with budget info.
    """
    with get_db() as db:
        today = datetime.now()
        # Get expenses for the category in the current month
        expenses_cat = ExpenseRepository.get_by_category_monthly(db, user_id, today.month, today.year)
        total_cat = next((item['total'] for item in expenses_cat if item['category'] == category), 0.0)
        
        # Get budget status
        budget_status = BudgetRepository.get_status(db, user_id, today.month, today.year)
        budget_cat = next((item for item in budget_status if item['category'] == category), None)
        
        result = {
            "total_spent": total_cat,
            "limit": 0.0,
            "percentage": 0.0,
            "alert": False,
            "alert_message": ""
        }
        
        if budget_cat and budget_cat['limit'] > 0:
            result["limit"] = budget_cat['limit']
            result["percentage"] = budget_cat['percentage']
            
            if result["percentage"] > 80:
                result["alert"] = True
                result["alert_message"] = "⚠️ *Atenção:* Você atingiu 80% do orçamento!"
                
        return result

async def check_anomaly(user_id: int, category: str, amount: float, description: str, expense_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Checks if the expense is an anomaly based on user history.
    """
    with get_db() as db:
        history = ExpenseRepository.get_category_history(db, user_id, category, days=30)
    
    if not history:
        return {"is_unusual": False}

    try:
        hist_str = json.dumps(
            [
                {
                    "date": g.date.isoformat(),
                    "amount": g.amount,
                    "description": g.description,
                }
                for g in history
            ],
            ensure_ascii=False
        )
        
        today = date.today()
        new_date = expense_date or today
        new_expense = json.dumps(
            {
                "date": new_date.isoformat(),
                "amount": amount,
                "description": description,
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
Novo gasto: {new_expense}
"""
        response_text = await generate_content(prompt)
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_text)
        
        # Translate keys to English for internal use
        return {
            "is_unusual": result.get("incomum", False),
            "reason": result.get("motivo", ""),
            "percentage_above": result.get("percentual_acima", 0)
        }
        
    except (json.JSONDecodeError, TypeError, Exception) as e:
        logger.warning(f"Failed to check anomaly: {e}", extra={"user_id": user_id, "category": category})
        return {"is_unusual": False}
