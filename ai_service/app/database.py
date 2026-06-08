from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

_db_path = Path(settings.SQLITE_DATABASE_PATH).expanduser()
if not _db_path.is_absolute():
    _db_path = (Path.cwd() / _db_path).resolve()
# Абсолютный путь: sqlite:////abs/path (четыре слэша после sqlite:)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_path.as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
