from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import Base


class AssistantMetric(Base):
    """Метрики для тестирования и отчёта (латентность, навигация)."""

    __tablename__ = "assistant_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    course_id = Column(String, nullable=True)
    duration_ms = Column(Float, nullable=True)
    success = Column(Integer, default=1)  # 1 ok, 0 fail
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
