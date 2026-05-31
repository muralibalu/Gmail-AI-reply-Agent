from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

# In Docker: DB lives in /app/data/ which is a mounted volume (persistent).
# Locally: falls back to ./draftly.db in the project root.
import os
DB_PATH = os.getenv("DB_PATH", "./draftly.db")
SQLITE_URL = f"sqlite:///{DB_PATH}"

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
