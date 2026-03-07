import asyncio
import time
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from finbot.whatsapp.client import WhatsAppClient
from finbot.whatsapp.state import StateManager
import finbot.whatsapp.webhook as webhook_mod


@pytest.mark.asyncio
async def test_send_message_success(monkeypatch):
    client = WhatsAppClient()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {"success": True}
    response.raise_for_status.return_value = None

    post_mock = AsyncMock(return_value=response)
    monkeypatch.setattr(client._http, "post", post_mock)

    result = await client.send_message("5511999999999", "Teste")

    assert result == {"success": True}
    called = post_mock.call_args.kwargs
    assert called["json"] == {"to": "5511999999999", "text": "Teste"}

    await client.close()


@pytest.mark.asyncio
async def test_send_message_retries_and_fails(monkeypatch):
    client = WhatsAppClient()

    post_mock = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
    monkeypatch.setattr(client._http, "post", post_mock)

    result = await client.send_message("5511999999999", "Teste", retries=2)

    assert result is None
    assert post_mock.await_count == 2

    await client.close()


def test_state_manager():
    sm = StateManager()
    user = "user1"

    assert sm.get_state(user) == "START"

    sm.set_state(user, "PROCESSANDO")
    assert sm.get_state(user) == "PROCESSANDO"

    sm.update_data(user, {"valor": 10})
    data = sm.get_data(user)
    assert data["valor"] == 10

    sm.clear_user(user)
    assert sm.get_state(user) == "START"


def test_webhook_enqueues_and_processes(monkeypatch):
    processed = []

    async def fake_process(payload, request_id):
        processed.append((request_id, payload.from_, payload.text))

    webhook_mod._PROCESSED_MESSAGES.clear()
    monkeypatch.setattr(webhook_mod, "process_payload", fake_process)

    with TestClient(webhook_mod.app) as client:
        response = client.post(
            "/webhook",
            json={
                "from": "5511999999999",
                "text": "oi",
                "name": "Teste",
                "message_id": "msg-1",
            },
        )
        assert response.status_code == 200
        time.sleep(0.1)

    assert len(processed) == 1
    assert processed[0][1] == "5511999999999"


def test_webhook_deduplicates_message_id(monkeypatch):
    processed = []

    async def fake_process(payload, request_id):
        processed.append((request_id, payload.message_id))

    webhook_mod._PROCESSED_MESSAGES.clear()
    monkeypatch.setattr(webhook_mod, "process_payload", fake_process)

    with TestClient(webhook_mod.app) as client:
        payload = {
            "from": "5511999999999",
            "text": "oi",
            "name": "Teste",
            "message_id": "dup-1",
        }
        first = client.post("/webhook", json=payload)
        second = client.post("/webhook", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        time.sleep(0.1)

    assert len(processed) == 1


def test_webhook_accepts_audio_payload(monkeypatch):
    processed = []

    async def fake_process(payload, request_id):
        processed.append((request_id, payload.media_type, payload.mime_type))

    webhook_mod._PROCESSED_MESSAGES.clear()
    monkeypatch.setattr(webhook_mod, "process_payload", fake_process)

    with TestClient(webhook_mod.app) as client:
        response = client.post(
            "/webhook",
            json={
                "from": "5511999999999",
                "text": "",
                "media_type": "audio",
                "mime_type": "audio/ogg",
                "media_base64": "ZmFrZQ==",
                "name": "Teste",
                "message_id": "audio-1",
            },
        )
        assert response.status_code == 200
        time.sleep(0.1)

    assert processed == [("audio-1", "audio", "audio/ogg")]
