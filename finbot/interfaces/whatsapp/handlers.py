import logging
import os
from .client import WhatsAppClient
from finbot.core.conversation.manager import conversation_manager
from finbot.services.report_service import ReportService
from finbot.database.connection import get_db
from finbot.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
client = WhatsAppClient()

async def handle_message(message_body):
    # message_body is a WhatsAppPayload object
    user_phone = message_body.from_  # WhatsApp Number
    text = message_body.text.strip()
    name = message_body.name
    
    # ID Conversion
    try:
        clean_id = user_phone.replace('@s.whatsapp.net', '')
        with get_db() as db:
            user = UserRepository.get_or_create_by_phone(db, clean_id, name)
            db_user_id = str(user.telegram_id) # Use string ID for consistency
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return

    # Simulate typing
    try:
        import httpx
        async with httpx.AsyncClient() as http_client:
            headers = {}
            adapter_api_key = os.getenv("WHATSAPP_ADAPTER_API_KEY", "")
            if adapter_api_key:
                headers["X-API-Key"] = adapter_api_key
            await http_client.post(
                "http://localhost:3000/send-state-typing",
                json={"to": user_phone},
                headers=headers
            )
    except Exception as e:
        logger.warning(f"Failed to send typing state: {e}")

    # Process via Conversation Manager
    response = await conversation_manager.handle_message(db_user_id, text)
    
    # Handle Special Actions
    final_text = response.text
    
    if response.action == "GENERATE_REPORT":
        # Generate report and append to text
        report_text = "Relatório não disponível."
        if "hoje" in text.lower() or "dia" in text.lower():
            report_text = ReportService.get_daily_report(int(db_user_id))
        elif "semana" in text.lower():
            report_text = ReportService.get_weekly_report(int(db_user_id))
        elif "mes" in text.lower() or "mês" in text.lower():
            report_text = ReportService.get_monthly_balance(int(db_user_id))
        else:
            report_text = ReportService.get_monthly_balance(int(db_user_id))
            
        final_text = report_text

    # Append suggestions
    if response.suggestions:
        final_text += "\n\n" + "\n".join([f"• {s}" for s in response.suggestions])

    await client.send_message(user_phone, final_text)
