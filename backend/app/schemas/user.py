from pydantic import BaseModel
from typing import Optional
from app.models.user import UserRole

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.student

class UserResponse(UserBase):
    id: int
    role: UserRole

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
