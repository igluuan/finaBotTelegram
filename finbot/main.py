import logging
import os
import sys
from telegram.ext import ApplicationBuilder, CommandHandler

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from finbot.config import TELEGRAM_BOT_TOKEN
from finbot.bot.database import crud
from finbot.bot.handlers import gasto, relatorio, dicas, config, parcela, ganho, cadastro, cartao

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def post_init(application):
    from finbot.bot.services.scheduler import start_scheduler
    from finbot.bot.handlers.whatsapp import start_webhook_server

    start_scheduler(application)
    await start_webhook_server()
    logger.info("Scheduler e webhook iniciados.")

def main():
    crud.init_db()
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não configurado. Defina a variável de ambiente antes de iniciar o bot.")
        raise SystemExit(1)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Cadastro Handler (substitui o start antigo)
    app.add_handler(cadastro.get_cadastro_handler())
    
    app.add_handler(CommandHandler("ajuda", config.ajuda))
    app.add_handler(CommandHandler("hoje", relatorio.hoje))
    app.add_handler(CommandHandler("semana", relatorio.semana))
    app.add_handler(CommandHandler("mes", relatorio.mes))
    app.add_handler(CommandHandler("categorias", relatorio.categorias))
    app.add_handler(CommandHandler("dica", dicas.dica))
    app.add_handler(CommandHandler("orcamento", config.orcamento))
    app.add_handler(CommandHandler("deletar", config.deletar))
    app.add_handler(CommandHandler("exportar", config.exportar))
    for handler in parcela.get_parcela_handlers():
        app.add_handler(handler)
    for handler in ganho.get_ganho_handlers():
        app.add_handler(handler)
    
    # Cartão Handlers
    for handler in cartao.get_cartao_handlers():
        app.add_handler(handler)
        
    for handler in gasto.get_gasto_handlers():
        app.add_handler(handler)
    logger.info("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main()
