import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.rag_service import get_rag_chain
from app.services.tts_service import synthesize_speech

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    voice: bool = False  # if True, also return TTS audio


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


async def stream_rag_response(message: str) -> AsyncIterator[str]:
    """Stream SSE tokens from RAG chain."""
    try:
        chain, retriever = get_rag_chain()
        # First retrieve sources
        source_docs = await retriever.ainvoke(message)
        sources = list({doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")})

        # Send sources first
        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        # Stream tokens
        async for token in chain.astream(message):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Chat error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint — tokens arrive in real time."""
    return StreamingResponse(
        stream_rag_response(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming endpoint — returns full answer at once."""
    try:
        chain, retriever = get_rag_chain()
        source_docs = await retriever.ainvoke(request.message)
        sources = list({doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")})
        answer = await chain.ainvoke(request.message)
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(request: ChatRequest):
    """Proxy to ElevenLabs. Returns MP3 or 204 (use browser TTS)."""
    audio = await synthesize_speech(request.message)
    if audio is None:
        from fastapi.responses import Response
        return Response(status_code=204)
    from fastapi.responses import Response
    return Response(content=audio, media_type="audio/mpeg")
