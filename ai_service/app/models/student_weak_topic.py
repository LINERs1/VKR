from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class StudentWeakTopic(Base):
    """Слабые темы ученика по ошибкам в тестах ДЗ."""

    __tablename__ = "student_weak_topics"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_id",
            "topic",
            name="uq_student_course_topic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("course_refs.id"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    lesson_id = Column(Integer, ForeignKey("lesson_refs.id"), nullable=True)
    wrong_count = Column(Integer, default=0, nullable=False)
    last_wrong_at = Column(DateTime, default=datetime.utcnow)
