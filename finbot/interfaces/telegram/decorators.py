from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from finbot.database.connection import get_db
from finbot.database.repositories.user_repository import UserRepository
from finbot.core.config import ALLOWED_USER_ID


def ensure_user(func):
    """
    Decorator to ensure the user exists in the database.
    If not, creates a basic record with Telegram ID and Name.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id

        # Apply access control on every request, not only on first registration.
        if ALLOWED_USER_ID and str(user_id) != str(ALLOWED_USER_ID):
            if update.message:
                await update.message.reply_text("⛔ Acesso não autorizado.")
            return

        with get_db() as db:
            user = UserRepository.get_by_telegram_id(db, user_id)
            if not user:
                UserRepository.create(db, user_id, update.effective_user.first_name)

        return await func(update, context, *args, **kwargs)

    return wrapper
