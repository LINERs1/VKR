import json
import logging
import base64
import re
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from app.config import settings
from app.services.rag_service import (
    get_retriever,
    get_chain,
    format_docs,
    format_history,
)
from app.services.tts_service import synthesize_speech

logger = logging.getLogger(__name__)
router = APIRouter()


class HistoryMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    voice: bool = False
    course_id: str = settings.DEFAULT_COURSE_ID
    course_name: str = ""
    page_context: dict = {}  # текущая страница, список курсов, etc.


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


# ---------------------------------------------------------------------------
# Streaming SSE
# ---------------------------------------------------------------------------

async def stream_rag_response(
    message: str,
    history: list[HistoryMessage],
    course_id: str,
    course_name: str,
    page_context: dict = {},
) -> AsyncIterator[str]:
    """
    Стримит SSE-токены от RAG-цепочки.
    Retriever вызывается ОДИН РАЗ — источники отправляются первыми.
    """
    try:
        retriever = get_retriever(course_id)
        source_docs = await retriever.ainvoke(message)
        sources = list(
            {doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")}
        )

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        context = format_docs(source_docs)
        history_text = format_history([m.model_dump() for m in history])
        chain = get_chain(course_name, course_id, page_context)

        full_response = ""
        display_buffer = ""
        
        async for token in chain.astream(
            {"context": context, "question": message, "history": history_text}
        ):
            full_response += token
            display_buffer += token
            
            # Если в буфере есть завершенный тег или мы не в процессе тега — чистим и отправляем
            if "[" in display_buffer:
                # Отправляем только то, что ДО скобки
                parts = display_buffer.split("[", 1)
                if parts[0]:
                    yield f"data: {json.dumps({'type': 'token', 'content': parts[0]})}\n\n"
                display_buffer = "[" + parts[1]
            else:
                yield f"data: {json.dumps({'type': 'token', 'content': display_buffer})}\n\n"
                display_buffer = ""

        # Сбрасываем остаток буфера, если это не начало тега
        if display_buffer and not display_buffer.startswith("["):
            yield f"data: {json.dumps({'type': 'token', 'content': display_buffer})}\n\n"

        # Ищем тег навигации в полном ответе
        nav_match = re.search(r'\[NAVIGATE:(.*?)\]', full_response)
        if nav_match:
            path = nav_match.group(1).strip()
            yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': path})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming — токены приходят в реальном времени."""
    return StreamingResponse(
        stream_rag_response(request.message, request.history, request.course_id, request.course_name, request.page_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_rag_voice_response(
    message: str,
    history: list[HistoryMessage],
    course_id: str,
    course_name: str,
    page_context: dict = {},
) -> AsyncIterator[str]:
    """
    Стримит SSE-токены и аудио-чанки (sentence-by-sentence) от RAG-цепочки.
    """
    try:
        retriever = get_retriever(course_id)
        source_docs = await retriever.ainvoke(message)
        sources = list(
            {doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")}
        )

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        context = format_docs(source_docs)
        history_text = format_history([m.model_dump() for m in history])
        chain = get_chain(course_name, course_id, page_context)

        sentence_buffer = ""
        full_response = ""
        display_buffer = ""
        # Простая регулярка для разбиения по предложениям.
        split_pattern = re.compile(r'([.!?\n]+)')

        async for token in chain.astream(
            {"context": context, "question": message, "history": history_text}
        ):
            full_response += token
            display_buffer += token
            
            # Логика скрытия тегов
            to_send = ""
            if "[" in display_buffer:
                parts = display_buffer.split("[", 1)
                to_send = parts[0]
                display_buffer = "[" + parts[1]
            else:
                to_send = display_buffer
                display_buffer = ""
            
            if to_send:
                yield f"data: {json.dumps({'type': 'token', 'content': to_send})}\n\n"
                sentence_buffer += to_send
                
                # Пытаемся найти конец предложения
                match = split_pattern.search(sentence_buffer)
                if match:
                    end_idx = match.end()
                    sentence = sentence_buffer[:end_idx].strip()
                    sentence_buffer = sentence_buffer[end_idx:]
                    
                    if sentence and any(c.isalpha() for c in sentence): # если есть буквы
                        # Синтезируем аудио
                        audio_bytes = await synthesize_speech(sentence)
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                            yield f"data: {json.dumps({'type': 'sentence', 'text': sentence, 'audio_b64': audio_b64})}\n\n"

        # Проверяем навигацию
        nav_match = re.search(r'\[NAVIGATE:(.*?)\]', full_response)
        if nav_match:
            path = nav_match.group(1).strip()
            yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': path})}\n\n"

        # Остаток
        sentence_buffer = sentence_buffer.strip()
        if sentence_buffer and any(c.isalpha() for c in sentence_buffer):
            audio_bytes = await synthesize_speech(sentence_buffer)
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield f"data: {json.dumps({'type': 'sentence', 'text': sentence_buffer, 'audio_b64': audio_b64})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.exception(f"Chat voice stream error:")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.post("/chat/voice")
async def chat_voice(request: ChatRequest):
    """SSE streaming с генерацией TTS по предложениям на лету."""
    return StreamingResponse(
        stream_rag_voice_response(request.message, request.history, request.course_id, request.course_name, request.page_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Не-стриминговый эндпоинт — возвращает полный ответ."""
    try:
        retriever = get_retriever(request.course_id)
        source_docs = await retriever.ainvoke(request.message)
        sources = list(
            {doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")}
        )
        context = format_docs(source_docs)
        history_text = format_history([m.model_dump() for m in request.history])
        chain = get_chain(request.course_name, request.course_id)
        answer = await chain.ainvoke(
            {"context": context, "question": request.message, "history": history_text}
        )
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(request: ChatRequest):
    """Синтез речи. Возвращает MP3 или 204 (браузерный TTS)."""
    audio = await synthesize_speech(request.message)
    if audio is None:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")
