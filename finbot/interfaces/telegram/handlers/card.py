from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from finbot.database.connection import get_db
from finbot.database.repositories.card_repository import CardRepository
from finbot.interfaces.telegram.decorators import ensure_user

@ensure_user
async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text("Use: /add_cartao [final 4 dígitos] [nome opcional]")
        return
        
    last_digits = args[0]
    if not last_digits.isdigit() or len(last_digits) != 4:
        await update.message.reply_text("❌ O final do cartão deve ter 4 dígitos.")
        return
        
    name = " ".join(args[1:]) if len(args) > 1 else None
    user_id = update.effective_user.id
    
    with get_db() as db:
        CardRepository.create(db, user_id, last_digits, name)
        
    msg = f"✅ Cartão final *{last_digits}* adicionado!"
    if name:
        msg += f" ({name})"
    await update.message.reply_text(msg, parse_mode="Markdown")

@ensure_user
async def list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    with get_db() as db:
        cards = CardRepository.get_all(db, user_id)
        
    if not cards:
        await update.message.reply_text("Nenhum cartão cadastrado.")
        return
        
    lines = ["💳 *Meus Cartões:*\n"]
    for c in cards:
        name = f" - {c.name}" if c.name else ""
        lines.append(f"• Final *{c.last_digits}*{name}")
        
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@ensure_user
async def delete_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text("Use: /del_cartao [final 4 dígitos]")
        return
        
    last_digits = args[0]
    user_id = update.effective_user.id
    
    with get_db() as db:
        success = CardRepository.delete(db, user_id, last_digits)
        
    if success:
        await update.message.reply_text(f"✅ Cartão final {last_digits} removido.")
    else:
        await update.message.reply_text("❌ Cartão não encontrado.")

def get_card_handlers():
    return [
        CommandHandler("add_cartao", add_card),
        CommandHandler("cartoes", list_cards),
        CommandHandler("del_cartao", delete_card),
    ]
