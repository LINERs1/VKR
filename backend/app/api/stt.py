"""
Speech-to-Text endpoint — универсальный STT для любого браузера.

Принимает аудио blob (webm/wav/ogg) и транскрибирует через Gemini.
Используется как fallback для Firefox/Safari, где нет Web Speech API.
"""

import logging
import base64

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class STTResponse(BaseModel):
    transcript: str


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Транскрибирует аудиофайл в текст через Gemini multimodal.

    Принимает: audio/webm, audio/wav, audio/ogg, audio/mp4 (любой формат MediaRecorder).
    Возвращает: { "transcript": "..." }
    """
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")

    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 100:
            return STTResponse(transcript="")

        # Определяем MIME-тип
        content_type = audio.content_type or "audio/webm"
        # Gemini принимает base64-кодированное аудио
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        transcript = await _transcribe_with_gemini(audio_b64, content_type)
        return STTResponse(transcript=transcript.strip())

    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _transcribe_with_gemini(audio_b64: str, mime_type: str) -> str:
    """Транскрипция через Gemini multimodal API."""
    import httpx

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": audio_b64,
                        }
                    },
                    {
                        "text": (
                            "Транскрибируй эту аудиозапись на русском языке. "
                            "Верни ТОЛЬКО текст того, что сказано, без пояснений, "
                            "без знаков препинания в начале и конце, без кавычек."
                        )
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 512,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return ""

    return parts[0].get("text", "").strip()
