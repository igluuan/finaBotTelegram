import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, filters

from finbot.core.conversation.manager import conversation_manager
from finbot.services.report_service import ReportService

logger = logging.getLogger(__name__)

async def unified_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Delegate to Conversation Manager
    response = await conversation_manager.handle_message(user_id, text)
    
    final_text = response.text
    
    # Handle Special Actions
    if response.action == "GENERATE_REPORT":
        report_text = "Relatório não disponível."
        if "hoje" in text.lower() or "dia" in text.lower():
            report_text = ReportService.get_daily_report(int(user_id))
        elif "semana" in text.lower():
            report_text = ReportService.get_weekly_report(int(user_id))
        elif "mes" in text.lower() or "mês" in text.lower():
            report_text = ReportService.get_monthly_balance(int(user_id))
        else:
            report_text = ReportService.get_monthly_balance(int(user_id))
            
        final_text = report_text
    
    # Handle Suggestions (Keyboard)
    reply_markup = ReplyKeyboardRemove()
    if response.suggestions:
        # Create a keyboard with suggestions
        # Max 2 buttons per row
        buttons = response.suggestions
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
    await update.message.reply_text(final_text, reply_markup=reply_markup)

def get_unified_handler():
    # Filter text messages that are NOT commands
    return MessageHandler(filters.TEXT & ~filters.COMMAND, unified_message_handler)
