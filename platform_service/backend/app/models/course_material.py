from sqlalchemy import Column, String, ForeignKey, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class CourseMaterial(Base):
    __tablename__ = "course_materials"

    id = Column(String, primary_key=True, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="methodology")
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course")
