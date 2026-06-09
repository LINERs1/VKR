import enum
import json

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

class HomeworkStatus(str, enum.Enum):
    pending = "pending"
    submitted = "submitted"
    graded = "graded"

class Homework(Base):
    __tablename__ = "homeworks"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)

    course = relationship("Course", back_populates="homeworks")
    teacher = relationship("User", foreign_keys=[teacher_id], back_populates="homeworks_given")
    assignments = relationship("HomeworkAssignment", back_populates="homework", cascade="all, delete-orphan")

class HomeworkAssignment(Base):
    __tablename__ = "homework_assignments"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homeworks.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    status = Column(String, default=HomeworkStatus.pending.value)
    student_code = Column(Text, nullable=True)
    student_text = Column(Text, nullable=True)
    student_quiz_json = Column(Text, nullable=True)
    teacher_feedback = Column(Text, nullable=True)
    grade = Column(Integer, nullable=True)
    ai_review_json = Column(Text, nullable=True)
    hint_count = Column(Integer, default=0, nullable=False)
    last_hint_at = Column(String, nullable=True)

    homework = relationship("Homework", back_populates="assignments")
    student = relationship("User", foreign_keys=[student_id], back_populates="homeworks_received")

    @property
    def student_quiz(self) -> dict | None:
        if not self.student_quiz_json:
            return None
        try:
            data = json.loads(self.student_quiz_json)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    @property
    def ai_review(self) -> dict | None:
        if not self.ai_review_json:
            return None
        try:
            data = json.loads(self.ai_review_json)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
