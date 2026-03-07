import json
from telegram import Update
from telegram.ext import ContextTypes
from finbot.services import ai_service
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.interfaces.telegram.decorators import ensure_user

@ensure_user
async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a financial tip based on user data."""
    user_id = update.effective_user.id
    
    await update.message.reply_chat_action("typing")
    
    # Get user context (expenses by category)
    from datetime import datetime
    now = datetime.now()
    
    with get_db() as db:
        expenses_cat = ExpenseRepository.get_by_category_monthly(db, user_id, now.month, now.year)
    
    context_data = {item['category']: item['total'] for item in expenses_cat}
    
    msg = await ai_service.answer_natural(
        "Me dê uma dica financeira baseada nos meus gastos deste mês.",
        context_data
    )
    
    await update.message.reply_text(f"💡 {msg}")
