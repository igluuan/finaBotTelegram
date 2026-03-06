from aiohttp import web
import aiohttp
import logging
import os

logger = logging.getLogger(__name__)

# Tenta importar config, lidando com diferentes contextos de execução
try:
    from finbot.config import WHATSAPP_ADAPTER_URL
except ImportError:
    # Fallback ou valor padrão se não estiver definido em config
    WHATSAPP_ADAPTER_URL = os.getenv("WHATSAPP_ADAPTER_URL", "http://localhost:3000/send-message")

async def webhook(request):
    try:
        data = await request.json()
        from_number = data.get("from", "").strip()
        text = data.get("text", "").strip()
        name = data.get("name", "Usuário")

        if not from_number or not text:
            return web.Response(status=400)

        logger.info(f"WhatsApp | {from_number} ({name}): {text}")

        # Imports locais para evitar ciclos
        from ..services.parser import parse_gasto
        from ..database.crud import get_or_create_user_by_phone, add_gasto

        resultado = await parse_gasto(text)

        if "erro" in resultado:
            await _responder(from_number, "❓ Não entendi. Tente: *35 uber* ou *almoço 20*")
            return web.Response(status=200)

        valor = float(str(resultado["valor"]).replace(",", "."))
        categoria = resultado["categoria"]
        descricao = resultado.get("descricao", "")

        user = get_or_create_user_by_phone(from_number, name)
        add_gasto(user.telegram_id, valor, categoria, descricao)

        await _responder(
            from_number,
            f"✅ R$ {valor:.2f} em *{categoria.capitalize()}* registrado!"
        )
        return web.Response(status=200)

    except Exception as e:
        logger.error(f"Erro no webhook WhatsApp: {e}", exc_info=True)
        return web.Response(status=500)


async def _responder(to: str, text: str):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                WHATSAPP_ADAPTER_URL,
                json={"to": to, "text": text},
                timeout=aiohttp.ClientTimeout(total=10)
            )
    except Exception as e:
        logger.error(f"Erro ao responder WhatsApp: {e}")


async def start_webhook_server():
    app = web.Application()
    app.router.add_post("/webhook", webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    # Porta 8000 deve coincidir com o docker-compose
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    logger.info("Webhook WhatsApp rodando na porta 8000")
