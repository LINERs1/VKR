from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class HomeworkStatus(str, Enum):
    pending = "pending"
    submitted = "submitted"
    graded = "graded"

class HomeworkAssignmentBase(BaseModel):
    student_id: int

class HomeworkAssignmentCreate(HomeworkAssignmentBase):
    pass

class HomeworkAssignmentResponse(HomeworkAssignmentBase):
    id: int
    homework_id: int
    status: HomeworkStatus
    student_code: Optional[str] = None
    student_text: Optional[str] = None
    teacher_feedback: Optional[str] = None
    grade: Optional[int] = None
    
    student_name: Optional[str] = None # Helper field to return frontend

    class Config:
        from_attributes = True

class HomeworkBase(BaseModel):
    course_id: str
    title: str
    description: str

class HomeworkCreate(HomeworkBase):
    student_ids: List[int]

class HomeworkResponse(HomeworkBase):
    id: int
    teacher_id: int
    assignments: List[HomeworkAssignmentResponse] = []

    class Config:
        from_attributes = True

class HomeworkSubmit(BaseModel):
    student_code: str
    student_text: str

class HomeworkGrade(BaseModel):
    teacher_feedback: str
    grade: int
