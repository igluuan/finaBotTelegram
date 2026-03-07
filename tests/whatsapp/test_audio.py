import os

import pytest

from finbot.whatsapp.handlers import _client, process_payload
from finbot.whatsapp.schemas import BaileysPayload
from finbot.services.audio_service import store_audio_payload, UPLOAD_DIR
from finbot.services.transcription_service import transcribe_audio


@pytest.mark.asyncio
async def test_process_audio_payload_saves_and_notifies(monkeypatch, tmp_path):
    sent_messages = []

    class DummyClient:
        async def send_message(self, to, text, retries=3):
            sent_messages.append((to, text))
            return {"success": True}

    monkeypatch.setattr(_client, "send_message", DummyClient().send_message)

    payload = BaileysPayload.model_validate(
        {
            "from": "5511999999999",
            "reply_to": "5511999999999@s.whatsapp.net",
            "text": "",
            "media_type": "audio",
            "mime_type": "audio/ogg",
            "media_base64": "ZmFrZQ==",
            "name": "Teste",
            "message_id": "audio-2",
        }
    )

    monkeypatch.setattr("finbot.whatsapp.handlers.transcribe_audio", lambda path: "teste")

    await process_payload(payload, "audio-2")

    assert sent_messages
    assert "Transcrição" in sent_messages[0][1]
    assert "audio_uploads" not in sent_messages[0][1]


def test_store_audio_payload_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("finbot.services.audio_service.UPLOAD_DIR", tmp_path)
    path = store_audio_payload("ZmFrZQ==", "audio/ogg", "5511999999999")
    assert path is not None
    assert tmp_path.joinpath(os.path.basename(path)).exists()


def test_process_audio_payload_skips_transcription(monkeypatch, tmp_path):
    sent_messages = []

    class DummyClient:
        async def send_message(self, to, text, retries=3):
            sent_messages.append((to, text))
            return {"success": True}

    monkeypatch.setattr(_client, "send_message", DummyClient().send_message)
    monkeypatch.setattr("finbot.whatsapp.handlers.store_audio_payload", lambda *args, **kwargs: str(tmp_path / "audio.ogg"))
    monkeypatch.setattr("finbot.whatsapp.handlers.transcribe_audio", lambda path: None)

    payload = BaileysPayload.model_validate(
        {
            "from": "5511999999999",
            "reply_to": "5511999999999@s.whatsapp.net",
            "text": "",
            "media_type": "audio",
            "mime_type": "audio/ogg",
            "media_base64": "ZmFrZQ==",
            "name": "Teste",
            "message_id": "audio-3",
        }
    )

    await process_payload(payload, "audio-3")

    assert sent_messages
    assert "Recebi seu áudio" in sent_messages[0][1]
