import base64
import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path("audio_uploads")


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def store_audio_payload(media_base64: str, mime_type: str | None, sender: str) -> str | None:
    """Save the incoming audio payload to disk for future transcription."""
    if not media_base64:
        return None

    _ensure_upload_dir()
    extension = "ogg"
    if mime_type and "/" in mime_type:
        extension = mime_type.split("/")[-1]
    filename = f"{sender}-{uuid.uuid4().hex}.{extension}"
    path = UPLOAD_DIR / filename
    try:
        data = base64.b64decode(media_base64)
        path.write_bytes(data)
        return str(path.resolve())
    except Exception:
        return None


def build_audio_unavailable_message(saved_path: str | None = None) -> str:
    base = (
        "Recebi seu áudio, mas a transcrição ainda não está habilitada neste servidor. "
        "Se puder, me envie a mesma informação em texto por enquanto."
    )
    if saved_path:
        base += f" Gravei o áudio aqui: {saved_path}"
    return base
