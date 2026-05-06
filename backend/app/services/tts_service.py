import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def synthesize_speech(text: str) -> bytes | None:
    """
    Synthesize speech via ElevenLabs streaming API.
    Returns MP3 bytes, or None if no API key (frontend uses browser TTS).
    """
    if not settings.ELEVENLABS_API_KEY:
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.content
            logger.error(f"ElevenLabs error: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"TTS request failed: {e}")

    return None
