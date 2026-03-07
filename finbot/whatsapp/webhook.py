import asyncio
import contextlib
import hashlib
import hmac
import logging
import time
import uuid

import httpx
from fastapi import FastAPI, Request, Response
from pydantic import ValidationError

from finbot.core.config import WHATSAPP_ADAPTER_URL, WHATSAPP_WEBHOOK_SECRET
from finbot.whatsapp.handlers import process_payload, shutdown as shutdown_handlers
from finbot.whatsapp.schemas import BaileysPayload

logger = logging.getLogger(__name__)

app = FastAPI(title="FinBot WhatsApp API")

_PROCESSED_MESSAGES: dict[str, float] = {}
_TTL_SECONDS = 60 * 10
_QUEUE_MAXSIZE = 1000
_WORKER_COUNT = 2

_message_queue: asyncio.Queue[tuple[str, BaileysPayload]] | None = None
_workers: list[asyncio.Task] = []


def _cleanup_old_messages(now_ts: float):
    expired = [mid for mid, ts in _PROCESSED_MESSAGES.items() if now_ts - ts > _TTL_SECONDS]
    for mid in expired:
        _PROCESSED_MESSAGES.pop(mid, None)


def _validate_signature(raw_body: bytes, provided_signature: str | None) -> bool:
    if not WHATSAPP_WEBHOOK_SECRET:
        return True
    if not provided_signature:
        return False

    digest = hmac.new(
        WHATSAPP_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, provided_signature)


async def _worker_loop(worker_id: int):
    assert _message_queue is not None
    while True:
        request_id, payload = await _message_queue.get()
        try:
            await process_payload(payload, request_id)
        except Exception as exc:
            logger.error("worker=%s request_id=%s unhandled error: %s", worker_id, request_id, exc)
        finally:
            _message_queue.task_done()


@app.on_event("startup")
async def startup_event():
    global _message_queue
    _message_queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    for index in range(_WORKER_COUNT):
        _workers.append(asyncio.create_task(_worker_loop(index + 1), name=f"whatsapp-worker-{index+1}"))


@app.on_event("shutdown")
async def shutdown_event():
    global _message_queue
    for worker in _workers:
        worker.cancel()
    for worker in _workers:
        with contextlib.suppress(asyncio.CancelledError):
            await worker
    _workers.clear()
    _message_queue = None
    await shutdown_handlers()


@app.get("/health")
async def health():
    queue_size = _message_queue.qsize() if _message_queue else 0
    return {"ok": True, "queue_size": queue_size, "workers": len(_workers)}


@app.get("/ready")
async def ready():
    if _message_queue is None:
        return Response(status_code=503)

    status_url = WHATSAPP_ADAPTER_URL.replace("/send-message", "/status")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
            response = await client.get(status_url)
            if response.status_code != 200:
                return Response(status_code=503)
    except Exception:
        return Response(status_code=503)

    return Response(status_code=200)


@app.post("/webhook")
async def webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Signature")

    if not _validate_signature(raw_body, signature):
        logger.warning("Webhook rejected due to invalid signature")
        return Response(status_code=401)

    try:
        payload = BaileysPayload.model_validate_json(raw_body)
    except (ValidationError, ValueError) as exc:
        logger.warning("Invalid WhatsApp payload: %s", exc)
        return Response(status_code=400)

    request_id = payload.message_id or str(uuid.uuid4())
    phone_tail = payload.from_[-4:] if len(payload.from_) >= 4 else payload.from_
    logger.info("request_id=%s incoming message phone_tail=%s", request_id, phone_tail)

    now_ts = time.time()
    _cleanup_old_messages(now_ts)
    if payload.message_id:
        if payload.message_id in _PROCESSED_MESSAGES:
            logger.info("request_id=%s duplicate ignored", request_id)
            return Response(status_code=200)
        _PROCESSED_MESSAGES[payload.message_id] = now_ts

    if _message_queue is None:
        logger.error("request_id=%s queue not initialized", request_id)
        return Response(status_code=503)

    try:
        _message_queue.put_nowait((request_id, payload))
    except asyncio.QueueFull:
        logger.error("request_id=%s queue full", request_id)
        return Response(status_code=503)

    return Response(status_code=200)
