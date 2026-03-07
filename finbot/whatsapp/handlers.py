import asyncio
import logging

from finbot.core.conversation.manager import conversation_manager
from finbot.database.connection import get_db
from finbot.database.repositories.user_repository import UserRepository
from finbot.services.audio_service import build_audio_unavailable_message, store_audio_payload
from finbot.services.report_service import ReportService
from finbot.whatsapp.client import WhatsAppClient
from finbot.whatsapp.schemas import BaileysPayload

logger = logging.getLogger(__name__)
_client = WhatsAppClient()


def _normalize_phone(phone: str) -> str:
    return phone.replace("@s.whatsapp.net", "").replace("@c.us", "").strip()


def _safe_report(user_id: int, text: str, structured_data: dict | None = None) -> str:
    structured_data = structured_data or {}
    category = structured_data.get("category")
    period = structured_data.get("period")
    metric = structured_data.get("metric")
    lowered = text.lower()

    if metric == "income":
        if not period:
            if "hoje" in lowered or "dia" in lowered:
                period = "today"
            elif "semana" in lowered:
                period = "week"
            else:
                period = "month"
        return ReportService.get_income_period_report(user_id, period)

    if category:
        if not period:
            if "hoje" in lowered or "dia" in lowered:
                period = "today"
            elif "semana" in lowered:
                period = "week"
            else:
                period = "month"
        return ReportService.get_category_period_report(user_id, category, period)

    if period == "today" or "hoje" in lowered or "dia" in lowered:
        return ReportService.get_daily_report(user_id)
    if period == "week" or "semana" in lowered:
        return ReportService.get_weekly_report(user_id)
    return ReportService.get_monthly_balance(user_id)


async def process_payload(payload: BaileysPayload, request_id: str) -> None:
    user_phone = _normalize_phone(payload.from_)
    reply_target = payload.reply_to or user_phone
    text = payload.text.strip()
    name = (payload.name or "Usuario").strip()

    if payload.media_type == "audio":
        logger.info("request_id=%s audio message received phone_tail=%s", request_id, user_phone[-4:])
        saved_path = store_audio_payload(payload.media_base64 or "", payload.mime_type, user_phone)
        await _client.send_message(reply_target, build_audio_unavailable_message(saved_path))
        return

    if not text:
        logger.info("request_id=%s ignored empty text/media_type=%s", request_id, payload.media_type)
        return

    try:
        with get_db() as db:
            user = UserRepository.get_or_create_by_phone(db, user_phone, name)
            internal_user_id = str(user.telegram_id)
    except Exception as exc:
        logger.error("request_id=%s failed user bootstrap: %s", request_id, exc)
        await _client.send_message(reply_target, "Nao consegui processar seu usuario agora. Tente novamente em instantes.")
        return

    await _client.send_typing(reply_target)

    fallback_text = "Tive um erro ao processar sua mensagem. Tente novamente em alguns segundos."
    try:
        response = await asyncio.wait_for(
            conversation_manager.handle_message(internal_user_id, text),
            timeout=25,
        )
    except asyncio.TimeoutError:
        logger.error("request_id=%s conversation timeout", request_id)
        await _client.send_message(reply_target, fallback_text)
        return
    except Exception as exc:
        logger.error("request_id=%s conversation failure: %s", request_id, exc)
        await _client.send_message(reply_target, fallback_text)
        return

    final_text = response.text or "Recebi sua mensagem."
    if response.action == "GENERATE_REPORT":
        try:
            final_text = _safe_report(int(internal_user_id), text, response.structured_data)
        except Exception as exc:
            logger.error("request_id=%s report failure: %s", request_id, exc)
            final_text = "Nao consegui gerar o relatorio agora. Tente novamente em instantes."

    if response.suggestions:
        suggestions_text = "\n".join([f"- {suggestion}" for suggestion in response.suggestions])
        final_text = f"{final_text}\n\n{suggestions_text}"

    sent = await _client.send_message(reply_target, final_text)
    if sent is None:
        logger.error("request_id=%s response not delivered phone_tail=%s", request_id, user_phone[-4:])


async def shutdown() -> None:
    await _client.close()
