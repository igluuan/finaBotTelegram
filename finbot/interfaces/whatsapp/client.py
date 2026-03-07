import httpx
import logging
import os

logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self):
        # Node.js service URL (configurable via env var)
        self.bridge_url = os.getenv("WHATSAPP_ADAPTER_URL", "http://localhost:3000/send-message")
        self.adapter_api_key = os.getenv("WHATSAPP_ADAPTER_API_KEY", "")

    async def send_message(self, to: str, text: str):
        payload = {
            "to": to,
            "text": text
        }
        headers = {}
        if self.adapter_api_key:
            headers["X-API-Key"] = self.adapter_api_key
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.bridge_url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error sending message via Bridge: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in Bridge Client: {e}")
                return None

    # Supports buttons, but current server.js implementation only supports text.
    # To maintain compatibility, we send as text for now.
    async def send_interactive_button(self, to: str, text: str, buttons: list):
        # Fallback: send text and list options
        options = "\n".join([f"- {btn['title']}" for btn in buttons])
        full_text = f"{text}\n\nOpções:\n{options}"
        return await self.send_message(to, full_text)
