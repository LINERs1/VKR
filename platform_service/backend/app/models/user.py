import enum
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default=UserRole.student.value)
    email = Column(String, nullable=True, default=None)
    full_name = Column(String, nullable=True, default=None)
    settings_json = Column(String, nullable=True, default="{}")

    homeworks_given = relationship("Homework", foreign_keys="[Homework.teacher_id]", back_populates="teacher")
    homeworks_received = relationship("HomeworkAssignment", foreign_keys="[HomeworkAssignment.student_id]", back_populates="student")
