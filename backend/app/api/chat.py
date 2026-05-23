import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.services.rag_service import get_retriever, get_chain, format_docs, format_history

logger = logging.getLogger(__name__)
router = APIRouter()

class HistoryMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    course_id: str = "course_1"  # Default course

class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []

async def retrieve_context_for_chat(message: str, course_id: str):
    retriever = get_retriever(course_id)
    source_docs = await retriever.ainvoke(message)
    sources = list(
        {doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")}
    )
    context = format_docs(source_docs)
    return source_docs, context, sources

async def _stream_tokens(chain, inputs: dict):
    full_response = ""
    async for token in chain.astream(inputs):
        full_response += token
        yield ('token', token)
    yield ('full', full_response)

async def stream_rag_response(
    message: str,
    history: list[HistoryMessage],
    course_id: str,
) -> AsyncIterator[str]:
    try:
        _docs, context, sources = await retrieve_context_for_chat(message, course_id)
        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        client_hist = [m.model_dump() for m in history]
        history_text = format_history(client_hist)
        chain = get_chain(course_id)

        async for event_type, content in _stream_tokens(
            chain, {"context": context, "question": message, "history": history_text}
        ):
            if event_type == 'token':
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Ошибка: {str(e)}'})}\n\n"

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return StreamingResponse(
        stream_rag_response(
            request.message, request.history, request.course_id
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        _docs, context, sources = await retrieve_context_for_chat(request.message, request.course_id)
        history_text = format_history([m.model_dump() for m in request.history])
        chain = get_chain(request.course_id)
        answer = await chain.ainvoke(
            {"context": context, "question": request.message, "history": history_text}
        )
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        from fastapi import HTTPException
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
