from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from finbot.database.connection import get_db
from finbot.database.repositories.user_repository import UserRepository
from finbot.interfaces.telegram.handlers import config_handler

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    with get_db() as db:
        existing = UserRepository.get_by_telegram_id(db, user_id)
        
        if not existing:
            UserRepository.create(db, user_id, user.first_name)
            
    # Reuse start message logic
    await config_handler.start(update, context)

def get_registration_handler():
    return CommandHandler("start", start_registration)
