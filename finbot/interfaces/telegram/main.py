import logging
import os
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from finbot.core.config import TELEGRAM_BOT_TOKEN
from finbot.database.connection import init_db
from finbot.services.scheduler_service import start_scheduler
from finbot.interfaces.telegram.handlers import (
    registration,
    config_handler,
    report,
    tips,
    installment,
    earning,
    card,
    expense,
    error_handler,
    unified
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def post_init(application):
    start_scheduler(application)
    logger.info("Scheduler started.")

def main():
    init_db()
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured.")
        raise SystemExit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Error Handler
    app.add_error_handler(error_handler.error_handler)
    
    # Registration (Start)
    app.add_handler(registration.get_registration_handler())
    
    # Config Handlers
    app.add_handler(CommandHandler("ajuda", config_handler.help_command))
    app.add_handler(CommandHandler("orcamento", config_handler.set_budget))
    app.add_handler(CommandHandler("deletar", config_handler.delete_last_expense))
    app.add_handler(CommandHandler("exportar", config_handler.export_data))
    
    # Report Handlers
    app.add_handler(CommandHandler("hoje", report.today))
    app.add_handler(CommandHandler("semana", report.week))
    app.add_handler(CommandHandler("mes", report.month))
    app.add_handler(CommandHandler("categorias", report.categories))
    
    # Tips Handler
    app.add_handler(CommandHandler("dica", tips.tip))
    
    # Installment Handlers (Keep only commands)
    installment_handlers = installment.get_installment_handlers()
    # app.add_handler(installment_handlers[0]) # Disable conversation
    for handler in installment_handlers[1:]:
        app.add_handler(handler)
        
    # Earning Handlers (Keep only commands)
    earning_handlers = earning.get_earning_handlers()
    # app.add_handler(earning_handlers[0]) # Disable conversation
    app.add_handler(earning_handlers[1])
        
    # Card Handlers
    for handler in card.get_card_handlers():
        app.add_handler(handler)
        
    # Expense Handlers (Conversation) -> REPLACED BY UNIFIED
    # for handler in expense.get_expense_handlers():
    #    app.add_handler(handler)
    
    # Unified Handler (Handles all text messages for conversation)
    app.add_handler(unified.get_unified_handler())
        
    logger.info("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
