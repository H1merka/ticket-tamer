"""Audio transcriber — speech-to-text for voice attachments.

Uses the OpenAI-compatible audio transcriptions API via RouterAI.
Falls back gracefully if the API doesn't support audio.

Supported formats: OGG, MP3, WAV, M4A, WEBM.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a", ".webm", ".oga", ".opus"}
AUDIO_CONTENT_TYPES = {
    "audio/ogg",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
    "audio/mp4",
    "audio/webm",
    "audio/opus",
}


def is_audio(content_type: str, filename: str = "") -> bool:
    """Check if a file is an audio attachment."""
    if content_type.lower() in AUDIO_CONTENT_TYPES:
        return True
    if filename:
        return Path(filename).suffix.lower() in AUDIO_EXTENSIONS
    return False


async def transcribe_audio(file_data: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio bytes via the OpenAI-compatible Whisper API.

    Returns the transcription text, or empty string on failure.
    """
    from agent.llm_client import get_client

    suffix = Path(filename).suffix or ".ogg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(file_data)
        tmp.close()

        client = get_client()
        with open(tmp.name, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
                response_format="text",
            )

        text = str(transcript).strip()
        logger.info("Transcribed %s: %d chars", filename, len(text))
        return text

    except Exception as exc:
        logger.warning(
            "Audio transcription failed for %s: %s. "
            "The RouterAI endpoint may not support audio.",
            filename,
            exc,
        )
        return ""
    finally:
        Path(tmp.name).unlink(missing_ok=True)
