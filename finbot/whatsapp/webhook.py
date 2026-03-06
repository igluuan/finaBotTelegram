from fastapi import FastAPI, BackgroundTasks, Response
from .schemas import BaileysPayload
from .handlers import handle_message
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="FinBot WhatsApp Baileys API")

@app.post("/webhook")
async def webhook(payload: BaileysPayload, background_tasks: BackgroundTasks):
    """
    Recebe mensagens do adaptador Baileys.
    """
    logger.info(f"Recebido webhook do Baileys: {payload.from_} - {payload.text}")
    background_tasks.add_task(handle_message, payload)
    return Response(status_code=200)
