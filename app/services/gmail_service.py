"""
GmailService — wraps the low-level gmail_client module.

Responsibilities:
  - Owns all Gmail API interactions for a specific user
  - Translates gmail_client errors into domain exceptions
  - One instance per request (created with a User object)
"""
from app.models import User
from app.gmail import gmail_client
from app.exceptions import GmailAPIError
from app.logger import get_logger

logger = get_logger(__name__)


class GmailService:
    def __init__(self, user: User):
        self._user = user
        logger.debug("GmailService initialised for user: %s", user.email)

    async def fetch_unread_emails(self, max_results: int = 20) -> list[dict]:
        logger.info("GmailService.fetch_unread_emails — user: %s | max: %d",
                    self._user.email, max_results)
        try:
            return await gmail_client.fetch_unread_emails(self._user, max_results)
        except Exception as e:
            logger.error("GmailService.fetch_unread_emails failed: %s", str(e))
            raise GmailAPIError(f"Failed to fetch inbox: {str(e)}")

    async def fetch_sent_emails(self, max_results: int = 10) -> list[str]:
        logger.info("GmailService.fetch_sent_emails — user: %s | max: %d",
                    self._user.email, max_results)
        try:
            return await gmail_client.fetch_sent_emails(self._user, max_results)
        except Exception as e:
            logger.warning("GmailService.fetch_sent_emails failed (non-fatal): %s", str(e))
            return []   # style context is optional — degrade gracefully

    async def send_reply(
        self,
        thread_id: str,
        original_message_id: str,
        to: str,
        subject: str,
        body: str,
    ) -> str:
        logger.info("GmailService.send_reply — user: %s | to: %s | subject: %s",
                    self._user.email, to, subject)
        try:
            return await gmail_client.send_reply(
                self._user, thread_id, original_message_id, to, subject, body
            )
        except Exception as e:
            logger.error("GmailService.send_reply failed: %s", str(e))
            raise GmailAPIError(f"Failed to send email: {str(e)}")
