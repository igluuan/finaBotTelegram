from fastapi import FastAPI, BackgroundTasks, Response, Request
from .schemas import BaileysPayload
from .handlers import handle_message
from ..config import WHATSAPP_WEBHOOK_SECRET
import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)

app = FastAPI(title="FinBot WhatsApp Baileys API")

# cache simples de idempotência em memória (curto prazo)
_PROCESSED_MESSAGES: dict[str, float] = {}
_TTL_SECONDS = 60 * 10


def _cleanup_old_messages(now_ts: float):
    expired = [mid for mid, ts in _PROCESSED_MESSAGES.items() if now_ts - ts > _TTL_SECONDS]
    for mid in expired:
        _PROCESSED_MESSAGES.pop(mid, None)


def _validate_signature(raw_body: bytes, provided_signature: str | None) -> bool:
    if not WHATSAPP_WEBHOOK_SECRET:
        # backward compatibility: se não houver segredo configurado, não bloqueia
        return True

    if not provided_signature:
        return False

    digest = hmac.new(
        WHATSAPP_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, provided_signature)


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe mensagens do adaptador Baileys.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")

    if not _validate_signature(raw_body, signature):
        logger.warning("Webhook rejeitado por assinatura inválida")
        return Response(status_code=401)

    payload = BaileysPayload.model_validate_json(raw_body)

    # Log com redução de PII (somente final do número)
    phone_tail = payload.from_[-4:] if len(payload.from_) >= 4 else payload.from_
    logger.info("Webhook recebido do WhatsApp final=%s", phone_tail)

    # Idempotência best-effort por message_id
    now_ts = time.time()
    _cleanup_old_messages(now_ts)
    if payload.message_id:
        if payload.message_id in _PROCESSED_MESSAGES:
            logger.info("Webhook duplicado ignorado: %s", payload.message_id)
            return Response(status_code=200)
        _PROCESSED_MESSAGES[payload.message_id] = now_ts

    background_tasks.add_task(handle_message, payload)
    return Response(status_code=200)
