from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class ChatMessage(Base):
    """История диалога с ассистентом (привязка к курсу и уроку)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    course_id = Column(String, default="default", nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lesson_refs.id"), nullable=True)
    call_id = Column(String, nullable=True, index=True)
    audio_url = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
