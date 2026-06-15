from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token, UpdateProfile, ChangePassword, UpdateSettings, ForgotPassword, ResetPassword
from app.services.auth_service import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user,
    SECRET_KEY,
    ALGORITHM
)
from jose import jwt, JWTError
from datetime import timedelta


router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system."
        )
    
    if user_in.email:
        email_exists = db.query(User).filter(User.email == user_in.email).first()
        if email_exists:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists."
            )
    
    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role="student"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_profile(
    body: UpdateProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить имя и email пользователя."""
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip() or None
    if body.email is not None:
        email = body.email.strip()
        if email and "@" not in email:
            raise HTTPException(status_code=422, detail="Некорректный email")
        # Проверяем уникальность
        if email:
            existing = db.query(User).filter(User.email == email, User.id != current_user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Этот email уже используется")
        current_user.email = email or None
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password")
def change_password(
    body: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Смена пароля — требует текущий пароль."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль неверен")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=422, detail="Новый пароль должен быть минимум 6 символов")
    current_user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"ok": True, "message": "Пароль успешно изменён"}

@router.put("/me/settings", response_model=UserResponse)
def update_settings(
    body: UpdateSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить настройки (JSON)."""
    current_user.settings_json = body.settings_json
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/students", response_model=list[UserResponse])
def get_students(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Not a teacher")
    return db.query(User).filter(User.role == "student").all()
@router.post("/forgot-password")
def forgot_password(body: ForgotPassword, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return {"ok": True, "message": "Если email существует, ссылка для сброса пароля отправлена."}
    
    expire = timedelta(minutes=30)
    reset_token = create_access_token(data={"sub": user.email, "type": "password_reset"}, expires_delta=expire)
    
    print(f"\n======================================")
    print(f"EMAIL SENT TO: {user.email}")
    print(f"RESET TOKEN: {reset_token}")
    print(f"======================================\n")
    
    return {"ok": True, "message": "Ссылка отправлена", "debug_token": reset_token}

@router.post("/reset-password")
def reset_password(body: ResetPassword, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(body.token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not email or token_type != "password_reset":
            raise HTTPException(status_code=400, detail="Неверный или просроченный токен")
    except JWTError:
        raise HTTPException(status_code=400, detail="Неверный или просроченный токен")
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
        
    if len(body.new_password) < 6:
        raise HTTPException(status_code=422, detail="Новый пароль должен быть минимум 6 символов")
        
    user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"ok": True, "message": "Пароль успешно сброшен"}
