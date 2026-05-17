from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import enum

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
    teacher_feedback = Column(Text, nullable=True)
    grade = Column(Integer, nullable=True)

    homework = relationship("Homework", back_populates="assignments")
    student = relationship("User", foreign_keys=[student_id], back_populates="homeworks_received")
