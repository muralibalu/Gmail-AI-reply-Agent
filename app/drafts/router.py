"""
Drafts router — thin HTTP layer only.

All draft business logic lives in DraftService.
This file only handles: HTTP routing, request/response schemas,
exception-to-HTTP mapping, and background task registration.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel

from app.services.draft_service import DraftService, SelectedEmailRequest
from app.dependencies import get_draft_service
from app.exceptions import DraftlyException
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


# ── Request / Response schemas ────────────────────────────────────────────────

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


class EmailPreviewOut(BaseModel):
    message_id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    body: str
    already_drafted: bool


class SelectedEmailIn(BaseModel):
    message_id: str
    instructions: str = ""


class GenerateIn(BaseModel):
    user_email: str
    tone: str = "formal"
    selected: List[SelectedEmailIn]


class EditDraftIn(BaseModel):
    draft_body: str


class RegenerateIn(BaseModel):
    instructions: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/inbox", response_model=List[EmailPreviewOut])
async def get_inbox(
    user_email: str,
    max_results: int = 20,
    draft_service: DraftService = Depends(get_draft_service),
):
    """Fetch unread emails as previews. No AI called — user selects which to draft."""
    try:
        previews = await draft_service.get_inbox(user_email, max_results)
        return [EmailPreviewOut(**vars(p)) for p in previews]
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in GET /drafts/inbox: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to fetch inbox")


@router.post("/generate", response_model=List[DraftOut])
async def generate_drafts(
    payload: GenerateIn,
    draft_service: DraftService = Depends(get_draft_service),
):
    """Generate AI drafts for selected emails with optional per-email instructions."""
    try:
        selected = [
            SelectedEmailRequest(message_id=s.message_id, instructions=s.instructions)
            for s in payload.selected
        ]
        drafts = await draft_service.generate_drafts(
            user_email=payload.user_email,
            tone=payload.tone,
            selected=selected,
        )
        return drafts
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in POST /drafts/generate: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Draft generation failed")


@router.get("/", response_model=List[DraftOut])
async def list_drafts(
    user_email: str,
    draft_service: DraftService = Depends(get_draft_service),
):
    """List all drafts for a user."""
    try:
        return await draft_service.list_drafts(user_email)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in GET /drafts/: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to list drafts")


@router.get("/{draft_id}", response_model=DraftOut)
async def get_draft(
    draft_id: int,
    draft_service: DraftService = Depends(get_draft_service),
):
    try:
        return await draft_service.get_draft(draft_id)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in GET /drafts/%d: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to fetch draft")


@router.patch("/{draft_id}/edit", response_model=DraftOut)
async def edit_draft(
    draft_id: int,
    payload: EditDraftIn,
    draft_service: DraftService = Depends(get_draft_service),
):
    try:
        return await draft_service.edit_draft(draft_id, payload.draft_body)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in PATCH /drafts/%d/edit: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to edit draft")


@router.post("/{draft_id}/approve", response_model=DraftOut)
async def approve_draft(
    draft_id: int,
    draft_service: DraftService = Depends(get_draft_service),
):
    try:
        return await draft_service.approve_draft(draft_id)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in POST /drafts/%d/approve: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to approve draft")


@router.post("/{draft_id}/reject", response_model=DraftOut)
async def reject_draft(
    draft_id: int,
    draft_service: DraftService = Depends(get_draft_service),
):
    try:
        return await draft_service.reject_draft(draft_id)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in POST /drafts/%d/reject: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to reject draft")


@router.post("/{draft_id}/regenerate", response_model=DraftOut)
async def regenerate_draft(
    draft_id: int,
    payload: RegenerateIn,
    draft_service: DraftService = Depends(get_draft_service),
):
    """Re-run AI generation with new user instructions on the original email."""
    try:
        return await draft_service.regenerate_draft(draft_id, payload.instructions)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in POST /drafts/%d/regenerate: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Regeneration failed")


@router.post("/{draft_id}/send", response_model=DraftOut)
async def send_draft(
    draft_id: int,
    background_tasks: BackgroundTasks,
    draft_service: DraftService = Depends(get_draft_service),
):
    """Validate and queue an approved draft for background sending."""
    try:
        draft = await draft_service.queue_send(draft_id)
        background_tasks.add_task(draft_service.send_with_retry, draft_id)
        logger.info("Send queued for draft id: %d", draft_id)
        return draft
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in POST /drafts/%d/send: %s", draft_id, str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to queue send")
