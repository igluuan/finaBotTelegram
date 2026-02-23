import logging
import os
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Garante que o diretório raiz do projeto esteja no sys.path quando rodar `python finbot/main.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from finbot.config import TELEGRAM_BOT_TOKEN
from finbot.bot.database import crud
from finbot.bot.handlers import gasto, relatorio, dicas, config, parcela, ganho

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application):
    from finbot.bot.services.scheduler import start_scheduler
    start_scheduler(application)
    logger.info("Scheduler iniciado.")

def main():
    # Init DB
    crud.init_db()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", config.start))
    app.add_handler(CommandHandler("ajuda", config.ajuda))
    app.add_handler(CommandHandler("hoje", relatorio.hoje))
    app.add_handler(CommandHandler("semana", relatorio.semana))
    app.add_handler(CommandHandler("mes", relatorio.mes))
    app.add_handler(CommandHandler("categorias", relatorio.categorias))
    app.add_handler(CommandHandler("dica", dicas.dica))
    app.add_handler(CommandHandler("orcamento", config.orcamento))
    app.add_handler(CommandHandler("deletar", config.deletar))
    app.add_handler(CommandHandler("exportar", config.exportar))

    # Parcelas Handlers
    for handler in parcela.get_parcela_handlers():
        app.add_handler(handler)
        
    # Ganhos Handlers
    for handler in ganho.get_ganho_handlers():
        app.add_handler(handler)
    
    # Message Handler (Text)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), gasto.handle_message))
    
    logger.info("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main()
