import httpx
import logging
import os

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self):
        # URL do serviço Node.js (agora configurável via variável de ambiente para Docker)
        self.baileys_url = os.getenv("WHATSAPP_ADAPTER_URL", "http://localhost:3000/send-message")
        self.adapter_api_key = os.getenv("WHATSAPP_ADAPTER_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def send_message(self, to: str, text: str):
        payload = {
            "to": to,
            "text": text
        }
        headers = {}
        if self.adapter_api_key:
            headers["X-API-Key"] = self.adapter_api_key

        try:
            response = await self._client.post(self.baileys_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro ao enviar mensagem via Baileys: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado no Baileys Client: {e}")
            return None

    # Baileys suporta botões, mas a implementação no server.js atual só suporta texto simples.
    # Para manter compatibilidade, enviamos como texto por enquanto.
    async def send_interactive_button(self, to: str, text: str, buttons: list):
        # Fallback: envia o texto e lista as opções
        opcoes = "\n".join([f"- {btn['title']}" for btn in buttons])
        full_text = f"{text}\n\nOpções:\n{opcoes}"
        return await self.send_message(to, full_text)
