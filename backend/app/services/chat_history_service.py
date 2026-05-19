"""Персистентная история чата с ассистентом."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage

CHAT_HISTORY_LIMIT = 40


def _lesson_id_from_context(page_context: dict | None) -> int | None:
    if not page_context:
        return None
    lid = page_context.get("lesson_id")
    if lid is None:
        return None
    try:
        return int(lid)
    except (TypeError, ValueError):
        return None


def save_exchange(
    db: Session,
    *,
    user_id: int,
    course_id: str,
    page_context: dict | None,
    user_message: str,
    assistant_message: str,
) -> None:
    if not user_id or not user_message.strip():
        return
    lesson_id = _lesson_id_from_context(page_context)
    cid = course_id or "default"
    db.add(
        ChatMessage(
            user_id=user_id,
            course_id=cid,
            lesson_id=lesson_id,
            role="user",
            content=user_message.strip()[:8000],
        )
    )
    if assistant_message.strip():
        db.add(
            ChatMessage(
                user_id=user_id,
                course_id=cid,
                lesson_id=lesson_id,
                role="assistant",
                content=assistant_message.strip()[:12000],
            )
        )
    db.commit()
    _trim_old(db, user_id, cid)


def _trim_old(db: Session, user_id: int, course_id: str) -> None:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id, ChatMessage.course_id == course_id)
        .order_by(ChatMessage.created_at.desc())
        .offset(CHAT_HISTORY_LIMIT)
        .all()
    )
    for r in rows:
        db.delete(r)
    if rows:
        db.commit()


def get_recent_history(
    db: Session,
    user_id: int,
    course_id: str,
    *,
    limit: int = 12,
) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id, ChatMessage.course_id == (course_id or "default"))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


def merge_history(
    client_history: list[dict],
    db_history: list[dict],
) -> list[dict]:
    """Объединяет БД-историю с переданной с клиента (клиент приоритетнее в хвосте)."""
    if not db_history:
        return client_history
    if not client_history:
        return db_history
    combined = db_history[-8:] + client_history[-6:]
    out: list[dict] = []
    for m in combined:
        if not m.get("content"):
            continue
        if out and out[-1]["role"] == m["role"] and out[-1]["content"] == m["content"]:
            continue
        out.append({"role": m["role"], "content": m["content"]})
    return out[-12:]
