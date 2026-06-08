from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class NotificationBase(BaseModel):
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool = False

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
