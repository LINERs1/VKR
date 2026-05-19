import hashlib
import io
import logging
logger = logging.getLogger(__name__)

import re

# Кэш озвучки (приветствие и повторяющиеся фразы)
_TTS_CACHE: dict[str, bytes] = {}
_TTS_CACHE_MAX = 64

def strip_emojis(text: str) -> str:
    """Удаляет эмодзи из текста, чтобы TTS их не озвучивал, сохраняя пунктуацию."""
    # Оставляем буквы, цифры, пробелы и основные знаки препинания
    return re.sub(r'[^\w\s.,!?;:()\-«»\"\'\n]', '', text)

def clean_text_for_tts(text: str) -> str:
    """Очищает текст от markdown разметки и спецсимволов перед озвучкой."""
    # Удаляем жирность и курсив (**text**, *text*, __text__, _text_)
    text = re.sub(r'[*_]{1,2}(.*?)[*_]{1,2}', r'\1', text)
    # Удаляем заголовки (# Заголовок)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # Удаляем маркеры списков (- item, * item, 1. item)
    text = re.sub(r'^[\-\*\•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    # Удаляем блоки кода
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Заменяем тире (одиночное или двойное) на пробелы, если оно висит отдельно
    text = re.sub(r'\s+[-—–]+\s+', ' ', text)
    # Очищаем лишние пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _tts_cache_key(text: str, provider: str, voice: str) -> str:
    digest = hashlib.sha256(f"{provider}|{voice}|{text}".encode("utf-8")).hexdigest()
    return digest


async def _synthesize_uncached(text: str) -> bytes | None:
    """
    Единая точка синтеза речи.
    Провайдер выбирается через TTS_PROVIDER в .env:
      edge        → Microsoft Edge TTS (бесплатно, хороший русский)
      elevenlabs  → ElevenLabs (платно, топ-качество)
      openai      → OpenAI TTS (платно)
    """
    from app.config import settings

    if not text or not text.strip():
        return None

    # Очищаем текст от эмодзи и markdown перед отправкой в TTS
    text = strip_emojis(text)
    text = clean_text_for_tts(text)
    if not text:
        return None

    provider = settings.TTS_PROVIDER.lower()

    if provider == "edge":
        return await _synthesize_edge(text, settings.TTS_VOICE)
    if provider == "silero":
        return await _synthesize_silero(text, settings.SILERO_VOICE)
    if provider == "f5":
        return await _synthesize_f5(text)
    if provider == "xtts":
        return await _synthesize_xtts(text)
    if provider == "elevenlabs":
        return await _synthesize_elevenlabs(text, settings.ELEVENLABS_API_KEY, settings.ELEVENLABS_VOICE_ID)
    if provider == "openai":
        return await _synthesize_openai(text, settings.OPENAI_API_KEY, settings.OPENAI_TTS_VOICE)

    logger.warning(f"Unknown TTS_PROVIDER '{provider}', falling back to edge-tts")
    return await _synthesize_edge(text, settings.TTS_VOICE)


async def synthesize_speech(text: str) -> bytes | None:
    """Синтез с кэшем для одинаковых фраз (приветствие и т.п.)."""
    from app.config import settings

    if not text or not text.strip():
        return None

    cleaned = strip_emojis(clean_text_for_tts(text))
    if not cleaned:
        return None

    provider = settings.TTS_PROVIDER.lower()
    voice_key = (
        settings.TTS_VOICE
        if provider == "edge"
        else settings.ELEVENLABS_VOICE_ID
        if provider == "elevenlabs"
        else settings.OPENAI_TTS_VOICE
        if provider == "openai"
        else settings.SILERO_VOICE
        if provider == "silero"
        else provider
    )
    key = _tts_cache_key(cleaned, provider, voice_key)
    if key in _TTS_CACHE:
        return _TTS_CACHE[key]

    audio = await _synthesize_uncached(text)
    if audio:
        if len(_TTS_CACHE) >= _TTS_CACHE_MAX:
            _TTS_CACHE.pop(next(iter(_TTS_CACHE)))
        _TTS_CACHE[key] = audio
    return audio


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

async def _synthesize_edge(text: str, voice: str) -> bytes | None:
    """
    Microsoft Edge TTS — бесплатно, без API-ключей.
    Хорошие русские голоса:
      ru-RU-SvetlanaNeural  — женский, чёткий (по умолчанию)
      ru-RU-DmitryNeural    — мужской
    """
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        audio = buf.getvalue()
        return audio if audio else None
    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        return None


async def _synthesize_elevenlabs(text: str, api_key: str, voice_id: str) -> bytes | None:
    """ElevenLabs TTS — платно, требует ELEVENLABS_API_KEY."""
    if not api_key:
        logger.warning("ElevenLabs: ELEVENLABS_API_KEY not set, skipping")
        return None
    try:
        import httpx
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        return None


async def _synthesize_openai(text: str, api_key: str, voice: str) -> bytes | None:
    """OpenAI TTS — платно, требует OPENAI_API_KEY."""
    if not api_key:
        logger.warning("OpenAI TTS: OPENAI_API_KEY not set, skipping")
        return None
    try:
        import httpx
        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": "tts-1", "input": text, "voice": voice}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.error(f"OpenAI TTS error: {e}")
        return None
# ---------------------------------------------------------------------------
# Silero TTS (Local)
# ---------------------------------------------------------------------------

_silero_model = None
_silero_device = None

async def _synthesize_silero(text: str, speaker: str) -> bytes | None:
    """
    Silero TTS — полностью локальный синтез. Качество русского голоса на высоте.
    Первый запуск скачает модель (~55MB).
    """
    global _silero_model, _silero_device
    from app.config import settings
    import os
    import torch
    import torch.package

    try:
        if _silero_model is None:
            logger.info("Initializing Silero TTS model...")
            # Silero любит CPU для стабильности и экономии VRAM
            _silero_device = torch.device('cpu') 
            
            model_url = "https://models.silero.ai/models/tts/ru/v4_ru.pt"
            model_path = settings.SILERO_MODEL_PATH
            
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            if not os.path.exists(model_path):
                logger.info(f"Downloading Silero model from {model_url}...")
                import requests
                r = requests.get(model_url)
                with open(model_path, 'wb') as f:
                    f.write(r.content)

            _silero_model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
            _silero_model.to(_silero_device)
            logger.info("Silero TTS initialized.")

        # Синтез (в отдельном потоке, так как torch блокирующий)
        import asyncio
        from functools import partial

        def _run_silero():
            audio = _silero_model.apply_tts(
                text=text,
                speaker=speaker,
                sample_rate=24000,
                put_accent=True,
                put_yo=True
            )
            
            # Конвертация тензора в WAV байты
            import soundfile as sf
            buf = io.BytesIO()
            sf.write(buf, audio.numpy(), 24000, format='WAV')
            return buf.getvalue()

        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(None, _run_silero)
        return audio_bytes

    except Exception as e:
        logger.error(f"Silero TTS error: {e}")
        return None


# ---------------------------------------------------------------------------
# F5-TTS (Voice Cloning)
# ---------------------------------------------------------------------------

_f5_model = None
_f5_cached_ref = None

async def _synthesize_f5(text: str) -> bytes | None:
    """
    F5-TTS — современное клонирование голоса с кешированием образца.
    """
    global _f5_model, _f5_cached_ref
    from app.config import settings
    import os
    import torch
    import asyncio
    from functools import partial

    try:
        # Принудительно добавляем путь к static-ffmpeg в PATH для pydub и f5-tts
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
        except:
            pass

        if _f5_model is None:
            logger.info("Initializing F5-TTS model (OFFLINE MODE)...")
            # Принудительно отключаем проверки обновлений в интернете
            os.environ["HF_HUB_OFFLINE"] = "1"
            
            from f5_tts.api import F5TTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Попробуем инициализировать модель в блоке try, 
            # чтобы увидеть реальную ошибку, если она есть
            try:
                _f5_model = F5TTS(device=device)
                logger.info(f"F5-TTS initialized on {device}.")
            except Exception as e:
                logger.error(f"F5-TTS loading failed: {e}")
                # Если офлайн-режим не сработал, пробуем вернуть онлайн на секунду
                os.environ["HF_HUB_OFFLINE"] = "0"
                return None

        ref_file = settings.F5_VOICE_REF
        if not os.path.exists(ref_file):
            logger.warning(f"F5-TTS: Reference file {ref_file} not found.")
            return None

        # Мы можем кешировать путь или данные, но в текущей реализации API f5-tts 
        # метод infer принимает путь. Чтобы ускорить, мы убеждаемся, что модель 
        # уже в VRAM/RAM (уже сделано выше). 
        # Если библиотека обновится и позволит передавать тензор — мы это добавим.
        
        def _run_f5():
            temp_out = "temp_f5_out.wav"
            # infer в f5-tts довольно оптимизирован, основное время ест сама генерация (ODE solver)
            _f5_model.infer(
                ref_file=ref_file,
                ref_text=settings.F5_VOICE_TEXT,
                gen_text=text,
                file_name=temp_out
            )
            if not os.path.exists(temp_out):
                return None
            with open(temp_out, "rb") as f:
                data = f.read()
            os.remove(temp_out)
            return data

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_f5)

    except Exception as e:
        logger.error(f"F5-TTS error: {e}")
        return None


# ---------------------------------------------------------------------------
# XTTS v2 (High-Quality Local Cloning)
# ---------------------------------------------------------------------------

_xtts_model = None

async def _synthesize_xtts(text: str) -> bytes | None:
    """
    XTTS v2 — Качественное локальное клонирование голоса.
    Первый запуск скачает модель (~1.5GB).
    """
    global _xtts_model
    from app.config import settings
    import os
    import torch
    import asyncio

    try:
        if _xtts_model is None:
            logger.info("Initializing XTTS v2 model (GPU AMD SUPPORT)...")
            
            import torch
            # XTTS v2 несовместима с DirectML (AMD GPU через Windows) — 
            # внутренние операции модели вызывают ошибку version_counter.
            # Используем CPU — на Python 3.11 это стабильно и достаточно быстро.
            device = torch.device("cpu")
            logger.info("XTTS v2 running on CPU (DirectML incompatible with this model).")

            from TTS.api import TTS
            
            # Инициализация модели XTTS v2
            _xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            logger.info(f"XTTS v2 initialized on {device}.")

        ref_file = settings.XTTS_VOICE_REF
        if not os.path.exists(ref_file):
            logger.warning(f"XTTS: Reference file {ref_file} not found. Voice cloning might fail.")
            return None

        def _run_xtts():
            import torch
            temp_out = "temp_xtts_out.wav"
            # Синтез в файл с отключением градиентов для стабильности на DirectML
            with torch.no_grad():
                _xtts_model.tts_to_file(
                    text=text,
                    speaker_wav=ref_file,
                    language="ru",
                    file_path=temp_out
                )
            if not os.path.exists(temp_out):
                return None
            with open(temp_out, "rb") as f:
                data = f.read()
            os.remove(temp_out)
            return data

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_xtts)

    except Exception as e:
        logger.error(f"XTTS v2 error: {e}")
        return None
