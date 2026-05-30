from app.models import Draft, DraftStatus, SendLog
from app.repositories.base import BaseRepository
from app.logger import get_logger

logger = get_logger(__name__)


class DraftRepository(BaseRepository[Draft]):
    model = Draft

    def get_by_user(self, user_email: str) -> list[Draft]:
        logger.debug("DraftRepository.get_by_user — user: %s", user_email)
        return self.db.query(Draft).filter(Draft.user_email == user_email).all()

    def get_by_message_id(self, message_id: str) -> Draft | None:
        logger.debug("DraftRepository.get_by_message_id — id: %s", message_id)
        return self.db.query(Draft).filter(Draft.gmail_message_id == message_id).first()

    def get_existing_message_ids(self, user_email: str) -> set[str]:
        """Return the set of Gmail message IDs that already have a draft for this user."""
        logger.debug("DraftRepository.get_existing_message_ids — user: %s", user_email)
        rows = (
            self.db.query(Draft.gmail_message_id)
            .filter(Draft.user_email == user_email)
            .all()
        )
        return {row.gmail_message_id for row in rows}

    def get_drafted_ids_for(self, message_ids: set[str]) -> set[str]:
        """Return which of the given message IDs already have a draft (any user)."""
        rows = (
            self.db.query(Draft.gmail_message_id)
            .filter(Draft.gmail_message_id.in_(message_ids))
            .all()
        )
        return {row.gmail_message_id for row in rows}

    def create_draft(
        self,
        user_email: str,
        gmail_message_id: str,
        thread_id: str,
        sender: str,
        subject: str | None,
        original_body: str,
        draft_body: str,
        tone: str,
    ) -> Draft:
        logger.debug("DraftRepository.create_draft — subject: %s | user: %s", subject, user_email)
        draft = Draft(
            user_email=user_email,
            gmail_message_id=gmail_message_id,
            thread_id=thread_id,
            sender=sender,
            subject=subject,
            original_body=original_body,
            draft_body=draft_body,
            tone=tone,
            status=DraftStatus.pending,
        )
        return self.save(draft)

    def update_status(self, draft: Draft, status: DraftStatus) -> Draft:
        logger.debug("DraftRepository.update_status — draft id: %d | status: %s",
                     draft.id, status)
        draft.status = status
        return self.save(draft)

    def update_body(self, draft: Draft, new_body: str, status: DraftStatus) -> Draft:
        logger.debug("DraftRepository.update_body — draft id: %d | new_length: %d",
                     draft.id, len(new_body))
        draft.draft_body = new_body
        draft.status = status
        return self.save(draft)

    def set_idempotency_key(self, draft: Draft, key: str) -> Draft:
        draft.send_idempotency_key = key
        return self.save(draft)

    def add_send_log(
        self,
        draft: Draft,
        attempt: int,
        status: str,
        error_message: str | None = None,
    ) -> SendLog:
        log = SendLog(
            draft_id=draft.id,
            user_email=draft.user_email,
            attempt=attempt,
            status=status,
            error_message=error_message,
        )
        self.db.add(log)
        self.db.commit()
        logger.debug("DraftRepository.add_send_log — draft id: %d | attempt: %d | status: %s",
                     draft.id, attempt, status)
        return log
