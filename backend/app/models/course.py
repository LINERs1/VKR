from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    icon = Column(String)
    color = Column(String)
    tags = Column(String)  # Stored as comma-separated string
    lessons_count = Column(Integer, default=0)
    duration = Column(String)
    students = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    instructor = Column(String)

    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")
    homeworks = relationship("Homework", back_populates="course", cascade="all, delete-orphan")

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    title = Column(String, nullable=False)
    duration = Column(String)
    content = Column(Text, nullable=False)  # Полный текст лекции/методички

    course = relationship("Course", back_populates="lessons")
