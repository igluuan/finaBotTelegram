import asyncio
import logging
from pathlib import Path
from typing import Optional

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def _ensure_model():
    global _model
    if _model is None and WhisperModel:
        _model = WhisperModel("small", device="cpu", compute_type="int8")


def transcribe_audio_sync(path: str) -> Optional[str]:
    _ensure_model()
    if _model is None:
        logger.warning("Whisper model unavailable; skipping transcription")
        return None

    try:
        segments, info = _model.transcribe(path, beam_size=5, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        logger.debug("Transcribed %s (%s sec)", path, info.duration)
        return text or None
    except Exception as exc:
        logger.error("Failed to transcribe %s: %s", path, exc)
        return None


async def transcribe_audio(path: str) -> Optional[str]:
    if not path:
        return None
    return await asyncio.to_thread(transcribe_audio_sync, path)
