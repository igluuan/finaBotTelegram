import logging
import asyncio
from datetime import date
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from finbot.database.connection import get_db
from finbot.database.repositories.earning_repository import EarningRepository
from finbot.interfaces.telegram.decorators import ensure_user

logger = logging.getLogger(__name__)

# States
AMOUNT, CATEGORY, DESCRIPTION, IS_RECURRING, RECEIPT_DAY = range(5)

async def start_add_earning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💵 Vamos registrar um ganho!\n\n"
        "Qual o *valor* recebido? (Ex: `3500.00`)",
        parse_mode="Markdown"
    )
    return AMOUNT

async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return AMOUNT
    
    context.user_data["amount"] = val
    await update.message.reply_text(
        "📂 Qual a *categoria*?\n"
        "(Ex: Salário, Freelance, Investimento, Presente)",
        parse_mode="Markdown"
    )
    return CATEGORY

async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text.strip().capitalize()
    await update.message.reply_text("📝 *Descrição* (opcional - digite '-' para pular):", parse_mode="Markdown")
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""
    context.user_data["description"] = desc
    
    await update.message.reply_text(
        "🔄 Esse ganho é *recorrente* (todo mês)?\nResponder: Sim ou Não",
        parse_mode="Markdown"
    )
    return IS_RECURRING

async def receive_is_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    is_rec = text in ["sim", "s", "yes", "y", "claro"]
    context.user_data["is_recurring"] = is_rec
    
    if is_rec:
        await update.message.reply_text("📅 Que *dia do mês* você costuma receber?", parse_mode="Markdown")
        return RECEIPT_DAY
    
    # Finalize if not recurring
    return await save_earning(update, context)

async def receive_receipt_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        day = int(update.message.text.strip())
        if day < 1 or day > 31:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Dia inválido.")
        return RECEIPT_DAY
        
    context.user_data["receipt_day"] = day
    return await save_earning(update, context)

async def save_earning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    user_id = update.effective_user.id
    
    def save():
        with get_db() as db:
            return EarningRepository.create(db, user_id, data)
            
    earning = await asyncio.to_thread(save)
    
    msg = (
        f"✅ Ganho de *R$ {earning.amount:.2f}* registrado!\n"
        f"📂 {earning.category}\n"
    )
    if earning.is_recurring:
        msg += f"🔄 Recorrente (Dia {earning.receipt_day})"
        
    await update.message.reply_text(msg, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelado.")
    return ConversationHandler.END

@ensure_user
async def list_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    def fetch():
        with get_db() as db:
            return EarningRepository.get_current_month_earnings(db, user_id)
            
    earnings = await asyncio.to_thread(fetch)
    
    if not earnings:
        await update.message.reply_text("Nenhum ganho registrado este mês.")
        return
        
    total = sum(e.amount for e in earnings)
    lines = ["💵 *Ganhos do Mês:*\n"]
    
    for e in earnings:
        rec = "🔄" if e.is_recurring else ""
        lines.append(f"• {e.category}: R$ {e.amount:.2f} {rec}")
        
    lines.append(f"\n💰 *Total: R$ {total:.2f}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def get_earning_handlers():
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_ganho", start_add_earning)],
        states={
            AMOUNT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            CATEGORY:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category)],
            DESCRIPTION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            IS_RECURRING: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_is_recurring)],
            RECEIPT_DAY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_receipt_day)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )
    return [
        conv,
        CommandHandler("ganhos", list_earnings)
    ]
