import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Draft, DraftStatus, User, SendLog
from app.gmail.gmail_client import fetch_unread_emails, fetch_sent_emails, send_reply
from app.ai.draft_generator import generate_draft
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])

MAX_SEND_RETRIES = 3


# ── Schemas ───────────────────────────────────────────────────────────────────

class DraftOut(BaseModel):
    id: int
    user_email: str
    gmail_message_id: str
    thread_id: str
    sender: str
    subject: Optional[str]
    draft_body: str
    tone: str
    status: str

    class Config:
        from_attributes = True


class EditDraftIn(BaseModel):
    draft_body: str


class SelectedEmail(BaseModel):
    message_id: str
    instructions: str = ""


class GenerateIn(BaseModel):
    user_email: str
    tone: str = "formal"
    selected: List[SelectedEmail]


class EmailPreview(BaseModel):
    message_id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    body: str
    already_drafted: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/inbox", response_model=List[EmailPreview])
def list_inbox(user_email: str, max_results: int = 20, db: Session = Depends(get_db)):
    """Fetch unread emails and return previews. No AI called here."""
    logger.info("Inbox fetch requested — user: %s | max: %d", user_email, max_results)

    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user or not user.access_token_enc:
            logger.warning("Unauthenticated inbox request for user: %s", user_email)
            raise HTTPException(status_code=401, detail="User not authenticated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error fetching user %s: %s", user_email, str(e))
        raise HTTPException(status_code=500, detail="Database error")

    # Fetch emails from Gmail — blocks the thread until complete
    try:
        emails = fetch_unread_emails(user, max_results=max_results)
    except Exception as e:
        logger.error("Failed to fetch inbox for user %s: %s", user_email, str(e))
        raise HTTPException(status_code=502, detail="Failed to fetch inbox from Gmail")

    # Fetch existing drafted IDs from DB — also blocks
    try:
        existing_ids = {
            row.gmail_message_id
            for row in db.query(Draft.gmail_message_id)
                         .filter(Draft.user_email == user_email)
                         .all()
        }
        logger.debug("Found %d already-drafted message IDs for user: %s",
                     len(existing_ids), user_email)
    except Exception as e:
        logger.error("DB error fetching existing draft IDs: %s", str(e))
        raise HTTPException(status_code=500, detail="Database error")

    previews = [
        EmailPreview(
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
    logger.info("Returning %d inbox preview(s) for user: %s", len(previews), user_email)
    return previews


@router.post("/generate", response_model=List[DraftOut])
def generate_drafts(payload: GenerateIn, db: Session = Depends(get_db)):
    """
    Generate AI draft replies for selected emails.
    Emails and AI calls are processed one-by-one (sequential/synchronous).
    """
    logger.info(
        "Draft generation requested — user: %s | tone: %s | selected: %d email(s)",
        payload.user_email, payload.tone, len(payload.selected),
    )

    try:
        user = db.query(User).filter(User.email == payload.user_email).first()
        if not user or not user.access_token_enc:
            logger.warning("Unauthenticated generate request for user: %s", payload.user_email)
            raise HTTPException(status_code=401, detail="User not authenticated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error fetching user %s: %s", payload.user_email, str(e))
        raise HTTPException(status_code=500, detail="Database error")

    if not payload.selected:
        raise HTTPException(status_code=400, detail="No emails selected")

    instructions_map = {s.message_id: s.instructions for s in payload.selected}
    selected_ids = set(instructions_map.keys())

    # Fetch inbox — blocks until Gmail responds
    logger.debug("Fetching inbox emails (blocking) — user: %s", payload.user_email)
    try:
        all_emails = fetch_unread_emails(user, max_results=50)
    except Exception as e:
        logger.error("Gmail inbox fetch failed: %s", str(e))
        raise HTTPException(status_code=502, detail="Failed to fetch emails from Gmail")

    # Fetch sent samples — blocks again (sequential, not parallel)
    logger.debug("Fetching sent emails for style context (blocking) — user: %s", payload.user_email)
    try:
        sent_samples = fetch_sent_emails(user, max_results=10)
    except Exception as e:
        logger.warning("Could not fetch sent samples (continuing): %s", str(e))
        sent_samples = []

    selected_emails = [e for e in all_emails if e["message_id"] in selected_ids]
    logger.debug("Matched %d/%d selected emails in inbox", len(selected_emails), len(selected_ids))

    if not selected_emails:
        raise HTTPException(status_code=404, detail="None of the selected emails were found in inbox")

    try:
        existing_ids = {
            row.gmail_message_id
            for row in db.query(Draft.gmail_message_id)
                         .filter(Draft.gmail_message_id.in_(selected_ids))
                         .all()
        }
    except Exception as e:
        logger.error("DB error checking existing drafts: %s", str(e))
        raise HTTPException(status_code=500, detail="Database error")

    created = []
    skipped = 0

    for email in selected_emails:
        if email["message_id"] in existing_ids:
            logger.debug("Skipping already-drafted message id: %s", email["message_id"])
            skipped += 1
            continue

        instructions = instructions_map.get(email["message_id"], "")
        if instructions:
            logger.info("User instructions for %s: %s", email["message_id"], instructions)

        # Each AI call blocks until OpenAI responds — done one at a time
        try:
            body = generate_draft(
                sender=email["sender"],
                subject=email["subject"],
                original_body=email["body"],
                tone=payload.tone,
                sent_email_samples=sent_samples,
                instructions=instructions,
            )
        except Exception as e:
            logger.error("Draft generation failed for message %s: %s",
                         email["message_id"], str(e))
            continue

        try:
            draft = Draft(
                user_email=payload.user_email,
                gmail_message_id=email["message_id"],
                thread_id=email["thread_id"],
                sender=email["sender"],
                subject=email["subject"],
                original_body=email["body"],
                draft_body=body,
                tone=payload.tone,
                status=DraftStatus.pending,
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)
            logger.info("Draft created — id: %d | subject: %s", draft.id, draft.subject)
            created.append(draft)
        except Exception as e:
            logger.error("DB error saving draft for message %s: %s",
                         email["message_id"], str(e))
            db.rollback()

    logger.info(
        "Generation complete — created: %d | skipped: %d | failed: %d | user: %s",
        len(created), skipped,
        len(selected_emails) - skipped - len(created),
        payload.user_email,
    )
    return created


@router.get("/", response_model=List[DraftOut])
def list_drafts(user_email: str, db: Session = Depends(get_db)):
    """List all drafts for a user."""
    logger.info("Listing drafts for user: %s", user_email)
    try:
        drafts = db.query(Draft).filter(Draft.user_email == user_email).all()
        logger.debug("Returned %d draft(s) for user: %s", len(drafts), user_email)
        return drafts
    except Exception as e:
        logger.error("DB error listing drafts for user %s: %s", user_email, str(e))
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    logger.debug("Fetching draft id: %d", draft_id)
    try:
        draft = db.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            logger.warning("Draft not found — id: %d", draft_id)
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error fetching draft id %d: %s", draft_id, str(e))
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/{draft_id}/regenerate", response_model=DraftOut)
def regenerate_draft(draft_id: int, payload: EditDraftIn, db: Session = Depends(get_db)):
    """Regenerate draft body with new instructions — sequential/blocking."""
    logger.info("Regenerate requested for draft id: %d", draft_id)

    try:
        draft = db.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            logger.warning("Regenerate failed — draft not found: id %d", draft_id)
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft.status == DraftStatus.sent:
            raise HTTPException(status_code=400, detail="Cannot regenerate a sent draft")

        user = db.query(User).filter(User.email == draft.user_email).first()
        if not user or not user.access_token_enc:
            raise HTTPException(status_code=401, detail="User not authenticated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error during regenerate setup for draft %d: %s", draft_id, str(e))
        raise HTTPException(status_code=500, detail="Database error")

    instructions = payload.draft_body
    logger.info("Regenerating draft id %d — instructions: %s", draft_id, instructions)

    # Fetch sent samples — blocks
    try:
        sent_samples = fetch_sent_emails(user, max_results=10)
    except Exception as e:
        logger.warning("Could not fetch sent samples for regeneration (continuing): %s", str(e))
        sent_samples = []

    # AI call — blocks
    try:
        new_body = generate_draft(
            sender=draft.sender,
            subject=draft.subject or "",
            original_body=draft.original_body or "",
            tone=draft.tone,
            sent_email_samples=sent_samples,
            instructions=instructions,
        )
    except Exception as e:
        logger.error("Regeneration AI call failed for draft id %d: %s", draft_id, str(e))
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    try:
        draft.draft_body = new_body
        draft.status = DraftStatus.pending
        db.commit()
        db.refresh(draft)
        logger.info("Draft id %d regenerated — new length: %d chars", draft_id, len(new_body))
        return draft
    except Exception as e:
        logger.error("DB error saving regenerated draft %d: %s", draft_id, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save regenerated draft")


@router.patch("/{draft_id}/edit", response_model=DraftOut)
def edit_draft(draft_id: int, payload: EditDraftIn, db: Session = Depends(get_db)):
    """Edit a draft body manually."""
    logger.info("Edit requested for draft id: %d", draft_id)
    try:
        draft = _get_pending_draft(draft_id, db)
        old_len = len(draft.draft_body)
        draft.draft_body = payload.draft_body
        draft.status = DraftStatus.edited
        db.commit()
        db.refresh(draft)
        logger.info("Draft id %d edited — old: %d chars | new: %d chars",
                    draft_id, old_len, len(draft.draft_body))
        return draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error editing draft id %d: %s", draft_id, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save edit")


@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve_draft(draft_id: int, db: Session = Depends(get_db)):
    """Approve a draft for sending."""
    logger.info("Approval requested for draft id: %d", draft_id)
    try:
        draft = _get_pending_draft(draft_id, db)
        draft.status = DraftStatus.approved
        db.commit()
        db.refresh(draft)
        logger.info("Draft id %d approved — subject: %s | user: %s",
                    draft_id, draft.subject, draft.user_email)
        return draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error approving draft id %d: %s", draft_id, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to approve draft")


@router.post("/{draft_id}/reject", response_model=DraftOut)
def reject_draft(draft_id: int, db: Session = Depends(get_db)):
    """Reject a draft."""
    logger.info("Rejection requested for draft id: %d", draft_id)
    try:
        draft = _get_pending_draft(draft_id, db)
        draft.status = DraftStatus.rejected
        db.commit()
        db.refresh(draft)
        logger.info("Draft id %d rejected — subject: %s | user: %s",
                    draft_id, draft.subject, draft.user_email)
        return draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error rejecting draft id %d: %s", draft_id, str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reject draft")


@router.post("/{draft_id}/send", response_model=DraftOut)
def send_draft(draft_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Queue an approved draft for sending in the background."""
    logger.info("Send requested for draft id: %d", draft_id)
    try:
        draft = db.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            logger.warning("Send failed — draft not found: id %d", draft_id)
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft.status not in (DraftStatus.approved, DraftStatus.edited):
            logger.warning("Send rejected — draft id %d has invalid status: %s",
                           draft_id, draft.status)
            raise HTTPException(status_code=400, detail="Only approved drafts can be sent")

        if not draft.send_idempotency_key:
            draft.send_idempotency_key = str(uuid.uuid4())
            db.commit()
            logger.debug("Assigned idempotency key to draft id %d: %s",
                         draft_id, draft.send_idempotency_key)

        user = db.query(User).filter(User.email == draft.user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info("Queuing background send task for draft id: %d", draft_id)
        background_tasks.add_task(_send_with_retry, draft.id, user, db)
        return draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error setting up send for draft id %d: %s", draft_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to queue send task")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_pending_draft(draft_id: int, db: Session) -> Draft:
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        logger.warning("Draft not found — id: %d", draft_id)
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status in (DraftStatus.sent, DraftStatus.rejected):
        logger.warning("Action blocked — draft id %d already has status: %s",
                       draft_id, draft.status)
        raise HTTPException(status_code=400, detail=f"Draft is already {draft.status}")
    return draft


def _send_with_retry(draft_id: int, user: User, db: Session):
    """Background task — send with retries, sequential/blocking."""
    try:
        draft = db.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            logger.error("Background send — draft id %d not found", draft_id)
            return
    except Exception as e:
        logger.error("DB error fetching draft for background send — id %d: %s", draft_id, str(e))
        return

    logger.info(
        "Background send started — draft id: %d | max attempts: %d | user: %s",
        draft_id, MAX_SEND_RETRIES, user.email,
    )

    for attempt in range(1, MAX_SEND_RETRIES + 1):
        logger.info("Send attempt %d/%d for draft id: %d", attempt, MAX_SEND_RETRIES, draft_id)
        try:
            send_reply(
                user=user,
                thread_id=draft.thread_id,
                original_message_id=draft.gmail_message_id,
                to=draft.sender,
                subject=draft.subject or "",
                body=draft.draft_body,
            )
            draft.status = DraftStatus.sent
            db.add(SendLog(
                draft_id=draft.id, user_email=draft.user_email,
                attempt=attempt, status="success",
            ))
            db.commit()
            logger.info("Draft id %d sent successfully on attempt %d", draft_id, attempt)
            return
        except Exception as e:
            logger.error("Send attempt %d/%d failed for draft id %d: %s",
                         attempt, MAX_SEND_RETRIES, draft_id, str(e))
            try:
                db.add(SendLog(
                    draft_id=draft.id, user_email=draft.user_email,
                    attempt=attempt, status="failed", error_message=str(e),
                ))
                db.commit()
            except Exception as db_err:
                logger.error("Failed to write SendLog for attempt %d: %s", attempt, str(db_err))
                db.rollback()

    logger.error("All %d send attempts exhausted for draft id %d — marking FAILED",
                 MAX_SEND_RETRIES, draft_id)
    try:
        draft.status = DraftStatus.failed
        db.commit()
    except Exception as e:
        logger.error("Failed to mark draft %d as FAILED: %s", draft_id, str(e))
        db.rollback()
