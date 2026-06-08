"""
Зеркальные модели платформы в БД ИИ-ассистента.
Хранят только id и title — используются для построения путей навигации.
Полные данные (тексты уроков, методички) хранятся на платформе и в ChromaDB.
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class CourseRef(Base):
    """
    Зеркало сущности Course с платформы.
    Хранит только id и title для генерации NavNode путей (/courses/{id}).
    """
    __tablename__ = "course_refs"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(200), nullable=False)

    # Связь с уроками-зеркалами
    lesson_refs = relationship("LessonRef", back_populates="course_ref", cascade="all, delete-orphan")


class LessonRef(Base):
    """
    Зеркало сущности Lesson с платформы.
    Хранит id, course_id и title для генерации NavNode путей (/courses/{course_id}?lesson={id}).
    """
    __tablename__ = "lesson_refs"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String(50), ForeignKey("course_refs.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)

    course_ref = relationship("CourseRef", back_populates="lesson_refs")
