from datetime import datetime
from sqlalchemy.orm import Session
from app.models import User
from app.repositories.base import BaseRepository
from app.logger import get_logger

logger = get_logger(__name__)


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        logger.debug("UserRepository.get_by_email — email: %s", email)
        return self.db.query(User).filter(User.email == email).first()

    def get_or_create(self, email: str) -> tuple[User, bool]:
        """Returns (user, created). created=True if a new record was inserted."""
        user = self.get_by_email(email)
        if user:
            logger.debug("UserRepository.get_or_create — found existing user: %s", email)
            return user, False
        logger.info("UserRepository.get_or_create — creating new user: %s", email)
        user = User(email=email)
        self.db.add(user)
        return user, True

    def update_tokens(
        self,
        user: User,
        access_token_enc: str,
        refresh_token_enc: str | None,
        token_expiry: datetime | None,
    ) -> User:
        logger.debug("UserRepository.update_tokens — user: %s", user.email)
        user.access_token_enc = access_token_enc
        if refresh_token_enc is not None:
            user.refresh_token_enc = refresh_token_enc
        user.token_expiry = token_expiry
        return self.save(user)

    def clear_tokens(self, user: User) -> User:
        logger.debug("UserRepository.clear_tokens — user: %s", user.email)
        user.access_token_enc = None
        user.refresh_token_enc = None
        user.token_expiry = None
        return self.save(user)

    def is_authenticated(self, user: User | None) -> bool:
        return user is not None and bool(user.access_token_enc)
