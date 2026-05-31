"""
FastAPI dependency injection wiring.

All services and repositories are constructed here and injected
into route handlers via Depends(). Routes never instantiate
these directly — they only declare what they need.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.draft_repository import DraftRepository
from app.services.ai_service import AIService
from app.services.auth_service import AuthService
from app.services.draft_service import DraftService


# ── Repository providers ──────────────────────────────────────────────────────

def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_draft_repo(db: Session = Depends(get_db)) -> DraftRepository:
    return DraftRepository(db)


# ── Service providers ─────────────────────────────────────────────────────────

def get_ai_service() -> AIService:
    """AIService is stateless — safe to create per request."""
    return AIService()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
) -> AuthService:
    return AuthService(user_repo=user_repo)


def get_draft_service(
    draft_repo: DraftRepository = Depends(get_draft_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    ai_service: AIService = Depends(get_ai_service),
) -> DraftService:
    return DraftService(
        draft_repo=draft_repo,
        user_repo=user_repo,
        ai_service=ai_service,
    )
