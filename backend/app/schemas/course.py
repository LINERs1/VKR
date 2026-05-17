from pydantic import BaseModel
from typing import List, Optional

class LessonResponse(BaseModel):
    id: int
    course_id: str
    title: str
    duration: Optional[str] = None
    content: str

    class Config:
        orm_mode = True
        from_attributes = True

class CourseResponse(BaseModel):
    id: str
    title: str
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None
    tags: List[str] = []
    lessons_count: int
    duration: Optional[str] = None
    students: int
    rating: float
    instructor: Optional[str] = None
    # We might not want to send all lessons content in the list view, but we can include them
    lessons: List[LessonResponse] = []

    class Config:
        orm_mode = True
        from_attributes = True
