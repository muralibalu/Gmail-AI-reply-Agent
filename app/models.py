from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone
import enum

Base = declarative_base()


class DraftStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"
    sent = "sent"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # OAuth tokens stored encrypted (Fernet)
    access_token_enc = Column(Text, nullable=True)
    refresh_token_enc = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False, index=True)
    gmail_message_id = Column(String, nullable=False)   # original email being replied to
    thread_id = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    original_body = Column(Text, nullable=True)
    draft_body = Column(Text, nullable=False)
    tone = Column(String, default="formal")
    status = Column(SAEnum(DraftStatus), default=DraftStatus.pending, nullable=False)
    send_idempotency_key = Column(String, unique=True, nullable=True)  # prevents double-send
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class SendLog(Base):
    __tablename__ = "send_logs"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, nullable=False, index=True)
    user_email = Column(String, nullable=False)
    attempt = Column(Integer, default=1)
    status = Column(String, nullable=False)   # "success" | "failed"
    error_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
