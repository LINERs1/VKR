from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class QuizItem(BaseModel):
    """Тест: один вопрос с вариантами ответа (один верный)."""

    question: str = ""
    options: List[str] = Field(default_factory=list)
    correct_index: Optional[int] = Field(default=0, description="Индекс верного варианта (0-based)")

    @field_validator("options", mode="before")
    @classmethod
    def normalize_options(cls, v):
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()]


class HomeworkTemplateContent(BaseModel):
    intro: str = ""
    code_filename: str = "solution.py"
    code_template: str = ""
    tests_code: str = ""
    quiz_items: List[QuizItem] = Field(default_factory=list)
    written_part: str = ""
    reference_code: str = ""


class HomeworkTemplateBase(BaseModel):
    course_id: str
    title: str
    content: HomeworkTemplateContent = Field(default_factory=HomeworkTemplateContent)


class HomeworkTemplateCreate(HomeworkTemplateBase):
    pass


class HomeworkTemplateUpdate(BaseModel):
    course_id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[HomeworkTemplateContent] = None


class HomeworkTemplateResponse(HomeworkTemplateBase):
    id: int
    teacher_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HomeworkTemplateListItem(BaseModel):
    id: int
    course_id: str
    title: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HomeworkTemplateAssign(BaseModel):
    student_ids: List[int]
