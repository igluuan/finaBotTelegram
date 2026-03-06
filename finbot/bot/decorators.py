from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from .database import crud

def garantir_usuario(func):
    """
    Decorator para garantir que o usuário existe no banco de dados.
    Se não existir, cria o registro básico com o ID e Nome do Telegram.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)
            
        user_id = update.effective_user.id
        
        # Verifica restrição de usuário em toda requisição (não só no primeiro cadastro)
        try:
            from ..config import ALLOWED_USER_ID
            if ALLOWED_USER_ID and str(user_id) != str(ALLOWED_USER_ID):
                if update.message:
                    await update.message.reply_text("⛔ Acesso não autorizado.")
                return
        except ImportError:
            pass

        user = crud.get_user(user_id)
        if not user:
            crud.create_user(user_id, update.effective_user.first_name)

        return await func(update, context, *args, **kwargs)
    return wrapper
