import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db

# TODO: Move to config/env
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-for-diplom-ai-123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 неделя

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

class DummyUser:
    def __init__(self, username: str, role: str, id: int, settings_json: str | None = None):
        self.username = username
        self.role = role
        self.id = id
        self.settings_json = settings_json

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "student")
        user_id: int = payload.get("id", 0)
        settings_json: str | None = payload.get("settings_json")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    return DummyUser(username=username, role=role, id=user_id, settings_json=settings_json)

from fastapi import Request

async def get_current_user_optional(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "student")
        user_id: int = payload.get("id", 0)
        settings_json: str | None = payload.get("settings_json")
        if not username:
            return None
        return DummyUser(username=username, role=role, id=user_id, settings_json=settings_json)
    except JWTError:
        return None

async def get_current_teacher(current_user: DummyUser = Depends(get_current_user)):
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
