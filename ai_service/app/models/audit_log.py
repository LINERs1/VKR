from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class AuditLog(Base):
    """Журнал действий ИИ для embeddable-интеграции и безопасности."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    resource = Column(String, nullable=True)
    success = Column(Integer, default=1)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
