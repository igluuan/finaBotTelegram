import logging
from typing import Any

import httpx

from finbot.core.config import WHATSAPP_ADAPTER_API_KEY, WHATSAPP_ADAPTER_URL

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self):
        self.adapter_url = WHATSAPP_ADAPTER_URL
        self.adapter_api_key = WHATSAPP_ADAPTER_API_KEY
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))

    async def close(self):
        await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.adapter_api_key:
            headers["X-API-Key"] = self.adapter_api_key
        return headers

    async def send_message(self, to: str, text: str, retries: int = 3) -> dict[str, Any] | None:
        payload = {"to": to, "text": text}

        for attempt in range(1, retries + 1):
            try:
                response = await self._http.post(
                    self.adapter_url,
                    json=payload,
                    headers=self._headers(),
                )

                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "Server error from WhatsApp adapter",
                        request=response.request,
                        response=response,
                    )

                if response.status_code in (401, 403):
                    logger.error("Adapter auth failure status=%s", response.status_code)
                    return None

                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "send_message attempt=%s/%s failed phone_tail=%s error=%s",
                    attempt,
                    retries,
                    to[-4:] if len(to) >= 4 else to,
                    str(exc),
                )
                if attempt == retries:
                    logger.error("send_message exhausted retries phone_tail=%s", to[-4:] if len(to) >= 4 else to)
                    return None
            except Exception as exc:
                logger.error("Unexpected send_message error: %s", exc)
                return None

    async def send_typing(self, to: str) -> bool:
        typing_url = self.adapter_url.replace("/send-message", "/send-state-typing")
        try:
            response = await self._http.post(
                typing_url,
                json={"to": to},
                headers=self._headers(),
            )
            if response.status_code >= 400:
                logger.info("Typing state not sent status=%s", response.status_code)
                return False
            return True
        except Exception as exc:
            logger.info("Typing state failed: %s", exc)
            return False
