"""Utilitários para monitorar e validar a disponibilidade do Ollama."""

import logging

import httpx

from finbot.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL


logger = logging.getLogger(__name__)
_ROOT_URL = OLLAMA_BASE_URL.rstrip("/")


async def ping_ollama(timeout: float = 2.0) -> dict:
    """Verifica se o Ollama responde e retorna sua versão."""

    url = f"{_ROOT_URL}/api/version"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=timeout / 2)) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return {
                "ok": True,
                "model": OLLAMA_MODEL,
                "version": data.get("version"),
                "endpoint": url,
            }
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)
        return {
            "ok": False,
            "model": OLLAMA_MODEL,
            "endpoint": url,
            "error": str(exc),
        }
