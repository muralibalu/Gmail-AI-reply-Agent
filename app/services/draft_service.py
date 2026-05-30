"""
DraftService — all draft-related business logic.

Responsibilities:
  - Orchestrate Gmail fetching + AI generation
  - Enforce state machine rules (pending → approved → sent)
  - Handle concurrent operations via asyncio.gather
  - Delegate data access to DraftRepository / UserRepository
  - Delegate external I/O to GmailService / AIService
"""
import asyncio
import uuid
from dataclasses import dataclass

from app.models import Draft, DraftStatus, User
from app.repositories.draft_repository import DraftRepository
from app.repositories.user_repository import UserRepository
from app.services.gmail_service import GmailService
from app.services.ai_service import AIService
from app.exceptions import (
    AuthenticationError, DraftNotFoundError, DraftAlreadySentError,
    DraftStatusError, NoEmailsSelectedError, EmailsNotFoundError,
    InvalidDraftStatusError, AIGenerationError, DatabaseError,
)
from app.logger import get_logger

logger = get_logger(__name__)

MAX_SEND_RETRIES = 3


@dataclass
class SelectedEmailRequest:
    message_id: str
    instructions: str = ""


@dataclass
class EmailPreviewDTO:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    body: str
    already_drafted: bool


class DraftService:
    def __init__(
        self,
        draft_repo: DraftRepository,
        user_repo: UserRepository,
        ai_service: AIService,
    ):
        self._draft_repo = draft_repo
        self._user_repo = user_repo
        self._ai = ai_service

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_inbox(self, user_email: str, max_results: int = 20) -> list[EmailPreviewDTO]:
        """
        Fetch unread emails and existing draft IDs concurrently,
        return enriched previews.
        """
        logger.info("DraftService.get_inbox — user: %s | max: %d", user_email, max_results)
        user = self._get_authenticated_user(user_email)
        gmail = GmailService(user)

        # Fetch emails and existing draft IDs in parallel
        emails, existing_ids = await asyncio.gather(
            gmail.fetch_unread_emails(max_results),
            asyncio.to_thread(
                self._draft_repo.get_existing_message_ids, user_email
            ),
        )

        previews = [
            EmailPreviewDTO(
                message_id=e["message_id"],
                thread_id=e["thread_id"],
                sender=e["sender"],
                subject=e["subject"] or "(no subject)",
                snippet=(e["body"] or "")[:120].replace("\n", " "),
                body=e["body"] or "",
                already_drafted=e["message_id"] in existing_ids,
            )
            for e in emails
        ]
        logger.info("DraftService.get_inbox — returning %d preview(s)", len(previews))
        return previews

    async def generate_drafts(
        self,
        user_email: str,
        tone: str,
        selected: list[SelectedEmailRequest],
    ) -> list[Draft]:
        """
        Fetch inbox + sent emails concurrently, then generate all selected
        drafts concurrently via asyncio.gather.
        """
        logger.info("DraftService.generate_drafts — user: %s | tone: %s | count: %d",
                    user_email, tone, len(selected))

        if not selected:
            raise NoEmailsSelectedError()

        user = self._get_authenticated_user(user_email)
        gmail = GmailService(user)
        instructions_map = {s.message_id: s.instructions for s in selected}
        selected_ids = set(instructions_map.keys())

        # Fetch inbox + sent emails in parallel
        logger.debug("DraftService.generate_drafts — fetching inbox + sent concurrently")
        all_emails, sent_samples = await asyncio.gather(
            gmail.fetch_unread_emails(max_results=50),
            gmail.fetch_sent_emails(max_results=10),
        )

        selected_emails = [e for e in all_emails if e["message_id"] in selected_ids]
        if not selected_emails:
            raise EmailsNotFoundError()

        existing_ids = await asyncio.to_thread(
            self._draft_repo.get_drafted_ids_for, selected_ids
        )
        to_generate = [e for e in selected_emails if e["message_id"] not in existing_ids]
        skipped = len(selected_emails) - len(to_generate)
        logger.info("DraftService.generate_drafts — to generate: %d | skipped: %d",
                    len(to_generate), skipped)

        if not to_generate:
            return []

        # Generate all drafts concurrently — all AI calls fire simultaneously
        logger.info("DraftService.generate_drafts — launching %d concurrent AI calls",
                    len(to_generate))
        results = await asyncio.gather(
            *[self._generate_one(e, instructions_map, tone, sent_samples)
              for e in to_generate],
            return_exceptions=True,
        )

        created = []
        for email, result in zip(to_generate, results):
            if isinstance(result, Exception):
                logger.error("DraftService.generate_drafts — failed for %s: %s",
                             email["message_id"], str(result))
                continue
            try:
                draft = await asyncio.to_thread(
                    self._draft_repo.create_draft,
                    user_email=user_email,
                    gmail_message_id=email["message_id"],
                    thread_id=email["thread_id"],
                    sender=email["sender"],
                    subject=email["subject"],
                    original_body=email["body"],
                    draft_body=result,
                    tone=tone,
                )
                logger.info("DraftService.generate_drafts — created draft id: %d | subject: %s",
                            draft.id, draft.subject)
                created.append(draft)
            except Exception as e:
                logger.error("DraftService.generate_drafts — DB save failed: %s", str(e))

        logger.info("DraftService.generate_drafts — done: created=%d skipped=%d failed=%d",
                    len(created), skipped, len(to_generate) - len(created))
        return created

    async def list_drafts(self, user_email: str) -> list[Draft]:
        logger.info("DraftService.list_drafts — user: %s", user_email)
        return await asyncio.to_thread(self._draft_repo.get_by_user, user_email)

    async def get_draft(self, draft_id: int) -> Draft:
        logger.debug("DraftService.get_draft — id: %d", draft_id)
        draft = await asyncio.to_thread(self._draft_repo.get_by_id, draft_id)
        if not draft:
            raise DraftNotFoundError(f"Draft {draft_id} not found")
        return draft

    async def edit_draft(self, draft_id: int, new_body: str) -> Draft:
        logger.info("DraftService.edit_draft — id: %d | new_length: %d", draft_id, len(new_body))
        draft = self._get_editable_draft(draft_id)
        old_len = len(draft.draft_body)
        updated = await asyncio.to_thread(
            self._draft_repo.update_body, draft, new_body, DraftStatus.edited
        )
        logger.info("DraftService.edit_draft — id: %d | %d→%d chars", draft_id, old_len, len(new_body))
        return updated

    async def approve_draft(self, draft_id: int) -> Draft:
        logger.info("DraftService.approve_draft — id: %d", draft_id)
        draft = self._get_editable_draft(draft_id)
        updated = await asyncio.to_thread(
            self._draft_repo.update_status, draft, DraftStatus.approved
        )
        logger.info("DraftService.approve_draft — id: %d approved", draft_id)
        return updated

    async def reject_draft(self, draft_id: int) -> Draft:
        logger.info("DraftService.reject_draft — id: %d", draft_id)
        draft = self._get_editable_draft(draft_id)
        updated = await asyncio.to_thread(
            self._draft_repo.update_status, draft, DraftStatus.rejected
        )
        logger.info("DraftService.reject_draft — id: %d rejected", draft_id)
        return updated

    async def regenerate_draft(self, draft_id: int, instructions: str) -> Draft:
        """Regenerate draft body with new user instructions using the original email."""
        logger.info("DraftService.regenerate_draft — id: %d | instructions: %s",
                    draft_id, instructions)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            raise DraftNotFoundError(f"Draft {draft_id} not found")
        if draft.status == DraftStatus.sent:
            raise DraftAlreadySentError()

        user = self._get_authenticated_user(draft.user_email)
        gmail = GmailService(user)
        sent_samples = await gmail.fetch_sent_emails()

        new_body = await self._ai.generate_draft(
            sender=draft.sender,
            subject=draft.subject or "",
            original_body=draft.original_body or "",
            tone=draft.tone,
            sent_email_samples=sent_samples,
            instructions=instructions,
        )
        updated = await asyncio.to_thread(
            self._draft_repo.update_body, draft, new_body, DraftStatus.pending
        )
        logger.info("DraftService.regenerate_draft — id: %d regenerated (%d chars)",
                    draft_id, len(new_body))
        return updated

    async def queue_send(self, draft_id: int) -> Draft:
        """Validate and prepare draft for sending. Actual send runs in background."""
        logger.info("DraftService.queue_send — id: %d", draft_id)
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            raise DraftNotFoundError(f"Draft {draft_id} not found")
        if draft.status not in (DraftStatus.approved, DraftStatus.edited):
            raise InvalidDraftStatusError()
        if not draft.send_idempotency_key:
            draft = await asyncio.to_thread(
                self._draft_repo.set_idempotency_key, draft, str(uuid.uuid4())
            )
            logger.debug("DraftService.queue_send — idempotency key assigned: %s",
                         draft.send_idempotency_key)
        return draft

    async def send_with_retry(self, draft_id: int) -> None:
        """
        Background task — send email with retries.
        Logs every attempt to SendLog table.
        """
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            logger.error("DraftService.send_with_retry — draft %d not found", draft_id)
            return

        user = self._user_repo.get_by_email(draft.user_email)
        if not user:
            logger.error("DraftService.send_with_retry — user %s not found", draft.user_email)
            return

        gmail = GmailService(user)
        logger.info("DraftService.send_with_retry — starting | draft: %d | max: %d",
                    draft_id, MAX_SEND_RETRIES)

        for attempt in range(1, MAX_SEND_RETRIES + 1):
            logger.info("DraftService.send_with_retry — attempt %d/%d | draft: %d",
                        attempt, MAX_SEND_RETRIES, draft_id)
            try:
                await gmail.send_reply(
                    thread_id=draft.thread_id,
                    original_message_id=draft.gmail_message_id,
                    to=draft.sender,
                    subject=draft.subject or "",
                    body=draft.draft_body,
                )
                await asyncio.to_thread(
                    self._draft_repo.update_status, draft, DraftStatus.sent
                )
                await asyncio.to_thread(
                    self._draft_repo.add_send_log, draft, attempt, "success"
                )
                logger.info("DraftService.send_with_retry — sent on attempt %d | draft: %d",
                            attempt, draft_id)
                return
            except Exception as e:
                logger.error("DraftService.send_with_retry — attempt %d failed: %s",
                             attempt, str(e))
                await asyncio.to_thread(
                    self._draft_repo.add_send_log, draft, attempt, "failed", str(e)
                )

        await asyncio.to_thread(
            self._draft_repo.update_status, draft, DraftStatus.failed
        )
        logger.error("DraftService.send_with_retry — all %d attempts exhausted | draft: %d",
                     MAX_SEND_RETRIES, draft_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_authenticated_user(self, user_email: str) -> User:
        user = self._user_repo.get_by_email(user_email)
        if not self._user_repo.is_authenticated(user):
            logger.warning("DraftService._get_authenticated_user — not authenticated: %s",
                           user_email)
            raise AuthenticationError()
        return user

    def _get_editable_draft(self, draft_id: int) -> Draft:
        draft = self._draft_repo.get_by_id(draft_id)
        if not draft:
            raise DraftNotFoundError(f"Draft {draft_id} not found")
        if draft.status in (DraftStatus.sent, DraftStatus.rejected):
            raise DraftStatusError(draft.status.value)
        return draft

    async def _generate_one(
        self,
        email: dict,
        instructions_map: dict[str, str],
        tone: str,
        sent_samples: list[str],
    ) -> str:
        instructions = instructions_map.get(email["message_id"], "")
        return await self._ai.generate_draft(
            sender=email["sender"],
            subject=email["subject"],
            original_body=email["body"],
            tone=tone,
            sent_email_samples=sent_samples,
            instructions=instructions,
        )
