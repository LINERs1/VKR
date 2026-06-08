from pydantic import BaseModel, EmailStr
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
    email: Optional[str] = None
    full_name: Optional[str] = None
    settings_json: Optional[str] = None

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UpdateProfile(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class UpdateSettings(BaseModel):
    settings_json: str
