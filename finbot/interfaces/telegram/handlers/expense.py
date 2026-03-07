import logging
import asyncio
from datetime import date
from typing import Optional, Dict, Any, List

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from finbot.services import parser_service, finance_service
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.card_repository import CardRepository
from finbot.interfaces.telegram.decorators import ensure_user
from finbot.interfaces.telegram import ui

logger = logging.getLogger(__name__)

# Conversation States
CONFIRM, ADJUST_CATEGORY, PAYMENT_METHOD, SELECT_CARD = range(4)

async def _process_amount(update: Update, value_str: str) -> Optional[float]:
    """Converts value string to float with basic validations."""
    try:
        val = float(value_str.replace(',', '.'))
        if val <= 0:
            await update.message.reply_text("❌ O valor deve ser maior que zero.")
            return None
        if val > 1_000_000:
            await update.message.reply_text("⚠️ Valor muito alto. Verifique se digitou corretamente.")
            return None
        return val
    except ValueError:
        await update.message.reply_text("Valor de gasto inválido.")
        return None

async def _confirm_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict[str, Any], confidence: float) -> Optional[int]:
    """
    If AI confidence is low, asks for user confirmation.
    Returns next state or None if confidence is high.
    """
    if confidence >= 0.7:
        return None

    msg = ui.format_confirmation_message(
        data['amount'],
        data['category'],
        data['description']
    )
    
    await update.message.reply_text(
        msg, 
        reply_markup=ui.expense_confirmation_keyboard()
    )
    return CONFIRM

@ensure_user
async def start_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: processes free text to extract expense."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    text = update.message.text
    await update.message.reply_chat_action("typing")
    
    # Parsing via AI or local fallback
    result = await parser_service.parse_expense(text)
    
    if "error" in result:
        await update.message.reply_text(
            "❓ Não entendi esse gasto. Tente algo como '35 uber' ou 'almoço 20'."
        )
        return ConversationHandler.END
        
    amount = result.get("amount")
    if isinstance(amount, str):
        amount = await _process_amount(update, amount)
        if amount is None:
            return ConversationHandler.END

    # Date extraction
    expense_date = parser_service.parse_user_date(text, today=date.today())
    
    # Store in context
    context.user_data["expense"] = {
        "user_id": update.effective_user.id,
        "amount": amount,
        "category": result.get("category"),
        "description": result.get("description", ""),
        "original_text": text,
        "date": expense_date,
    }
    
    # Check AI confidence
    confirm_state = await _confirm_ai(
        update, 
        context, 
        context.user_data["expense"], 
        result.get("confidence", 0)
    )
    
    if confirm_state is not None:
        return confirm_state
    
    return await ask_payment_method(update, context)

async def ask_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks for payment method."""
    data = context.user_data["expense"]
    
    await update.message.reply_text(
        f"💰 Pagamento de *R$ {data['amount']:.2f}* ({data['category']}).\n"
        "Qual foi a forma de pagamento?",
        parse_mode="Markdown",
        reply_markup=ui.payment_method_keyboard()
    )
    return PAYMENT_METHOD

async def _fetch_cards(user_id: int, filter_type: str) -> List[Any]:
    """Fetches user cards filtering by type (credit/debit)."""
    # Execute in separate thread as it's sync DB operation
    def get_cards():
        with get_db() as db:
            cards = CardRepository.get_all(db, user_id)
            
            # Fallback for old cards without full registration
            if not cards:
                finals = CardRepository.get_unique_used_cards(db, user_id)
                if finals:
                    # Create objects compatible with card structure
                    cards = [
                        type('SimpleCard', (object,), {'last_digits': f, 'name': None, 'type': 'both'})
                        for f in finals
                    ]
            return cards

    cards = await asyncio.to_thread(get_cards)
            
    return [
        c for c in cards 
        if c.type == 'both' or c.type == filter_type
    ]

async def ask_card(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_type: str):
    """Shows list of available cards for the selected payment type."""
    user_id = context.user_data["expense"]["user_id"]
    filter_type = "credit" if "Crédito" in payment_type else "debit"
    
    valid_cards = await _fetch_cards(user_id, filter_type)
    
    # If no cards, use generic method and finalize
    if not valid_cards:
        context.user_data["expense"]["method"] = payment_type
        await _finalize_expense(update, context)
        return ConversationHandler.END

    # Create buttons for cards
    buttons = []
    for c in valid_cards:
        label = f" {c.name} ({c.last_digits})" if c.name else f" ({c.last_digits})"
        buttons.append(f"💳{label}")

    # Organize in 2 columns grid
    menu = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    menu.append(["Voltar"])
    
    await update.message.reply_text(
        f"Selecione o cartão de *{payment_type}*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(menu, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_CARD

async def receive_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes payment method choice."""
    text = update.message.text.strip()
    
    if text == "Pular":
        context.user_data["expense"]["method"] = None
        await _finalize_expense(update, context)
        return ConversationHandler.END

    # Clean emojis and normalize
    clean_text = text.replace("💠 ", "").replace("💵 ", "").replace("💳 ", "")
    
    if clean_text in ["Crédito", "Débito"]:
        return await ask_card(update, context, clean_text)
        
    context.user_data["expense"]["method"] = clean_text
    await _finalize_expense(update, context)
    return ConversationHandler.END

async def receive_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes specific card choice."""
    text = update.message.text.strip()
    
    if text == "Voltar":
        return await ask_payment_method(update, context)
        
    # Remove emoji "💳 "
    method = text.replace("💳 ", "")
    
    context.user_data["expense"]["method"] = method
    await _finalize_expense(update, context)
    return ConversationHandler.END

async def confirm_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes AI confirmation response."""
    if not update.message:
        return ConversationHandler.END
        
    text = update.message.text.strip().lower()
    
    if "confirmar" in text or "✅" in text or "sim" in text:
        return await ask_payment_method(update, context)
        
    if "trocar" in text or "✏" in text:
        await update.message.reply_text(
            "Escolha a categoria correta para este gasto:",
            reply_markup=ui.expense_categories_keyboard()
        )
        return ADJUST_CATEGORY
        
    if "cancelar" in text or "❌" in text:
        return await cancel(update, context)
        
    await update.message.reply_text(
        "Ok, não registrei esse gasto. Tente enviar novamente com mais detalhes.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.pop("expense", None)
    return ConversationHandler.END

async def adjust_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes manual category change."""
    if not update.message:
        return ConversationHandler.END
        
    choice = update.message.text.strip()
    new_category = finance_service.get_category_key(choice)
    
    if not new_category:
        await update.message.reply_text(
            "Escolha uma categoria válida usando o teclado.",
            reply_markup=ui.expense_categories_keyboard()
        )
        return ADJUST_CATEGORY
        
    context.user_data["expense"]["category"] = new_category
    return await ask_payment_method(update, context)

def _save_expense_db(data: Dict[str, Any]):
    """Helper function to save to DB (executed in thread)."""
    with get_db() as db:
        ExpenseRepository.create(
            db,
            data["user_id"], 
            data["amount"], 
            data["category"], 
            data["description"], 
            payment_method=data.get("method"), 
            date_record=data.get("date")
        )

async def _finalize_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizes registration, saves to DB and sends feedback."""
    data = context.user_data.get("expense")
    if not data:
        return

    # Save to DB (separate thread to avoid blocking)
    await asyncio.to_thread(_save_expense_db, data)
    
    # Check budget
    # Using thread for check_budget might be safer if it does heavy DB work, 
    # but check_budget logic is relatively fast. keeping asyncio.to_thread for consistency.
    def check_budget_sync():
        return finance_service.check_budget(
            data["user_id"],
            data["category"],
            data["amount"]
        )
    
    budget_status = await asyncio.to_thread(check_budget_sync)
    
    # Send success message
    msg = ui.format_success_expense_message(
        data["amount"],
        data["category"],
        budget_status["total_spent"],
        budget_status["limit"],
        budget_status["percentage"]
    )
    
    if budget_status["alert"]:
        msg += f"\n{budget_status['alert_message']}"
        
    if update.message:
        await update.message.reply_text(
            msg, 
            parse_mode='Markdown', 
            reply_markup=ReplyKeyboardRemove()
        )
    
    # Check anomaly in background (doesn't block final response if fails)
    try:
        anomaly_result = await finance_service.check_anomaly(
            data["user_id"],
            data["category"],
            data["amount"],
            data["description"],
            data.get("date")
        )
        
        if anomaly_result.get("is_unusual"):
            reason = anomaly_result.get("reason", "")
            await update.message.reply_text(
                f"⚠️ Gasto incomum detectado: {reason}",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error checking anomaly: {e}", exc_info=True)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels current operation."""
    context.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "❌ Registro cancelado.", 
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

def get_expense_handlers():
    """Configures and returns conversation handlers."""
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, start_expense)],
        states={
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_expense)],
            ADJUST_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, adjust_category)],
            PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payment_method)],
            SELECT_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_card)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        conversation_timeout=300
    )
    return [conv]
