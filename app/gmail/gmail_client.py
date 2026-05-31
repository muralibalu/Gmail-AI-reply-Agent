import asyncio
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.models import User
from app.security import decrypt_token
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


def _get_credentials(user: User) -> Credentials:
    """Build and refresh Gmail OAuth2 credentials synchronously."""
    logger.debug("Building Gmail credentials for user: %s", user.email)
    try:
        creds = Credentials(
            token=decrypt_token(user.access_token_enc),
            refresh_token=decrypt_token(user.refresh_token_enc) if user.refresh_token_enc else None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
        )
    except Exception as e:
        logger.error("Failed to build credentials for user %s: %s", user.email, str(e))
        raise

    if creds.expired and creds.refresh_token:
        logger.info("Access token expired — refreshing for user: %s", user.email)
        try:
            creds.refresh(Request())
            logger.info("Token refreshed successfully for user: %s", user.email)
        except Exception as e:
            logger.error("Token refresh failed for user %s: %s", user.email, str(e))
            raise

    return creds


def _fetch_single_email(service, msg_id: str) -> Dict | None:
    """Fetch one email's full detail. Returns None on failure."""
    try:
        detail = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        body = _extract_body(detail["payload"])
        logger.debug(
            "Fetched email — id: %s | subject: %s | from: %s | body_len: %d",
            detail["id"], headers.get("Subject", "(none)"),
            headers.get("From", ""), len(body),
        )
        return {
            "message_id": detail["id"],
            "thread_id": detail["threadId"],
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "body": body,
            "timestamp": detail.get("internalDate"),
        }
    except Exception as e:
        logger.error("Failed to fetch details for message id %s: %s", msg_id, str(e))
        return None


# ── Sync internals (run inside thread pool via asyncio.to_thread) ─────────────

def _sync_fetch_unread_emails(user: User, max_results: int) -> List[Dict]:
    logger.debug("_sync_fetch_unread_emails started — user: %s | max: %d", user.email, max_results)
    creds = _get_credentials(user)
    service = build("gmail", "v1", credentials=creds)

    try:
        results = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
        ).execute()
    except Exception as e:
        logger.error("Gmail list (inbox) API failed for user %s: %s", user.email, str(e))
        raise

    messages = results.get("messages", [])
    logger.info("Found %d unread message(s) in inbox for user: %s", len(messages), user.email)

    emails = [_fetch_single_email(service, m["id"]) for m in messages]
    fetched = [e for e in emails if e is not None]
    logger.info("Successfully fetched %d/%d email(s) for user: %s",
                len(fetched), len(messages), user.email)
    return fetched


def _sync_fetch_sent_emails(user: User, max_results: int) -> List[str]:
    logger.debug("_sync_fetch_sent_emails started — user: %s | max: %d", user.email, max_results)
    creds = _get_credentials(user)
    service = build("gmail", "v1", credentials=creds)

    try:
        results = service.users().messages().list(
            userId="me", labelIds=["SENT"], maxResults=max_results
        ).execute()
    except Exception as e:
        logger.error("Gmail list (sent) API failed for user %s: %s", user.email, str(e))
        raise

    messages = results.get("messages", [])
    logger.debug("Found %d sent message(s) for user: %s", len(messages), user.email)

    sent = []
    for msg in messages:
        try:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            body = _extract_body(detail["payload"])
            if body:
                sent.append(body)
        except Exception as e:
            logger.warning("Could not fetch sent message %s: %s", msg["id"], str(e))

    logger.info("Collected %d sent email(s) for style context — user: %s", len(sent), user.email)
    return sent


def _sync_send_reply(user: User, thread_id: str, original_message_id: str,
                     to: str, subject: str, body: str) -> str:
    logger.debug("_sync_send_reply started — user: %s | to: %s", user.email, to)
    creds = _get_credentials(user)
    service = build("gmail", "v1", credentials=creds)

    message = MIMEMultipart()
    message["To"] = to
    message["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    message["In-Reply-To"] = original_message_id
    message["References"] = original_message_id
    message.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        sent = service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
        logger.info("Email sent successfully — Gmail message id: %s", sent["id"])
        return sent["id"]
    except Exception as e:
        logger.error("Gmail send API failed — user: %s | thread: %s | error: %s",
                     user.email, thread_id, str(e))
        raise


# ── Public async API ──────────────────────────────────────────────────────────
# Each offloads its blocking Google API call to a thread pool so the
# FastAPI event loop is never blocked waiting on network I/O.

async def fetch_unread_emails(user: User, max_results: int = 10) -> List[Dict]:
    """Async wrapper — fetches unread emails without blocking the event loop."""
    logger.info("Fetching up to %d unread emails for user: %s", max_results, user.email)
    return await asyncio.to_thread(_sync_fetch_unread_emails, user, max_results)


async def fetch_sent_emails(user: User, max_results: int = 10) -> List[str]:
    """Async wrapper — fetches sent emails without blocking the event loop."""
    logger.info("Fetching up to %d sent emails for style learning — user: %s", max_results, user.email)
    return await asyncio.to_thread(_sync_fetch_sent_emails, user, max_results)


async def send_reply(user: User, thread_id: str, original_message_id: str,
                     to: str, subject: str, body: str) -> str:
    """Async wrapper — sends email without blocking the event loop."""
    logger.info("Sending reply — user: %s | to: %s | subject: %s | thread: %s",
                user.email, to, subject, thread_id)
    return await asyncio.to_thread(
        _sync_send_reply, user, thread_id, original_message_id, to, subject, body
    )


def _extract_body(payload: Dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning("Failed to decode email body part: %s", str(e))
                return ""
        return ""

    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text

    return ""
