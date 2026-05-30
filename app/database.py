from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

SQLITE_URL = "sqlite:///./draftly.db"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
