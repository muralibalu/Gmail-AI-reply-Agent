"""
Custom exception hierarchy for Draftly.

Routers catch these and map them to HTTP responses.
Services raise these instead of HTTPException — keeping HTTP concerns
out of the business logic layer.
"""
from fastapi import HTTPException, status


class DraftlyException(Exception):
    """Base exception for all Draftly domain errors."""
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)

    def to_http(self) -> HTTPException:
        return HTTPException(status_code=self.http_status, detail=self.message)


# ── Auth exceptions ───────────────────────────────────────────────────────────

class AuthenticationError(DraftlyException):
    http_status = status.HTTP_401_UNAUTHORIZED
    default_message = "User not authenticated"


class InvalidOAuthState(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "Invalid or expired OAuth2 state"


class TokenEncryptionError(DraftlyException):
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "Failed to process authentication tokens"


class TokenExchangeError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "OAuth2 token exchange failed"


class UserinfoFetchError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "Could not retrieve user info from Google"


# ── User exceptions ───────────────────────────────────────────────────────────

class UserNotFoundError(DraftlyException):
    http_status = status.HTTP_404_NOT_FOUND
    default_message = "User not found"


class UserSessionError(DraftlyException):
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "Failed to store user session"


# ── Draft exceptions ──────────────────────────────────────────────────────────

class DraftNotFoundError(DraftlyException):
    http_status = status.HTTP_404_NOT_FOUND
    default_message = "Draft not found"


class DraftAlreadySentError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "Cannot modify a sent draft"


class DraftStatusError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, status_value: str):
        super().__init__(f"Draft is already {status_value}")


class NoEmailsSelectedError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "No emails selected"


class EmailsNotFoundError(DraftlyException):
    http_status = status.HTTP_404_NOT_FOUND
    default_message = "None of the selected emails were found in inbox"


class InvalidDraftStatusError(DraftlyException):
    http_status = status.HTTP_400_BAD_REQUEST
    default_message = "Only approved drafts can be sent"


# ── External service exceptions ───────────────────────────────────────────────

class GmailAPIError(DraftlyException):
    http_status = status.HTTP_502_BAD_GATEWAY
    default_message = "Failed to communicate with Gmail API"


class AIGenerationError(DraftlyException):
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "AI draft generation failed"


class DatabaseError(DraftlyException):
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "A database error occurred"
