"""
AuthService — all OAuth2 and user-session business logic.

Responsibilities:
  - Build and cache OAuth2 flows (PKCE state management)
  - Exchange authorization code for tokens
  - Fetch and verify Google user identity
  - Create/update user records with encrypted tokens
  - Revoke tokens on logout
"""
import asyncio
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from app.models import User
from app.repositories.user_repository import UserRepository
from app.security import encrypt_token, decrypt_token
from app.config import settings
from app.exceptions import (
    InvalidOAuthState, TokenExchangeError, UserinfoFetchError,
    UserNotFoundError, UserSessionError,
)
from app.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# In-memory PKCE state store: { state -> Flow }
_flow_store: dict[str, Flow] = {}


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    # ── Public methods ────────────────────────────────────────────────────────

    def build_authorization_url(self) -> tuple[str, str]:
        """
        Build an OAuth2 consent URL with PKCE.
        Returns (auth_url, state) — state must be stored and verified in callback.
        """
        logger.info("AuthService.build_authorization_url — building OAuth2 flow")
        try:
            flow = self._build_flow()
            auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
            _flow_store[state] = flow
            logger.debug("Flow stored — state: %s | total pending: %d",
                         state, len(_flow_store))
            return auth_url, state
        except Exception as e:
            logger.error("AuthService.build_authorization_url failed: %s", str(e))
            raise

    async def handle_callback(self, code: str, state: str) -> str:
        """
        Exchange OAuth2 code for tokens, fetch user email, upsert user record.
        Returns the authenticated user's email.
        """
        logger.info("AuthService.handle_callback — state: %s", state)

        flow = _flow_store.pop(state, None)
        if not flow:
            logger.error("No flow for state=%s — CSRF or expired session", state)
            raise InvalidOAuthState()

        creds = await self._exchange_code(flow, code)
        email = await self._fetch_user_email(creds)
        await self._upsert_user(email, creds)
        return email

    async def logout(self, user_email: str) -> None:
        """Revoke Google token and clear stored credentials."""
        logger.info("AuthService.logout — user: %s", user_email)

        user = self._user_repo.get_by_email(user_email)
        if not user:
            logger.warning("AuthService.logout — user not found: %s", user_email)
            raise UserNotFoundError(f"User not found: {user_email}")

        await self._revoke_token(user)

        try:
            self._user_repo.clear_tokens(user)
            logger.info("AuthService.logout — tokens cleared for user: %s", user_email)
        except Exception as e:
            logger.error("AuthService.logout — DB error clearing tokens: %s", str(e))
            raise UserSessionError("Failed to clear user session")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_flow(self) -> Flow:
        client_config = {
            "web": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uris": [settings.gmail_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        return Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=settings.gmail_redirect_uri,
        )

    async def _exchange_code(self, flow: Flow, code: str) -> Credentials:
        logger.debug("AuthService._exchange_code — exchanging code (offloaded to thread)")
        try:
            await asyncio.to_thread(flow.fetch_token, code=code)
            logger.debug("AuthService._exchange_code — token expiry: %s", flow.credentials.expiry)
            return flow.credentials
        except Exception as e:
            logger.error("AuthService._exchange_code failed: %s", str(e))
            raise TokenExchangeError(f"OAuth2 token exchange failed: {str(e)}")

    async def _fetch_user_email(self, creds: Credentials) -> str:
        logger.debug("AuthService._fetch_user_email — fetching Google userinfo")
        try:
            import google.auth.transport.requests

            def _fetch():
                session = google.auth.transport.requests.AuthorizedSession(creds)
                return session.get("https://www.googleapis.com/oauth2/v2/userinfo").json()

            userinfo = await asyncio.to_thread(_fetch)
            email = userinfo["email"]
            logger.info("AuthService._fetch_user_email — email: %s | verified: %s",
                        email, userinfo.get("verified_email"))
            return email
        except Exception as e:
            logger.error("AuthService._fetch_user_email failed: %s", str(e))
            raise UserinfoFetchError(f"Could not retrieve user info: {str(e)}")

    async def _upsert_user(self, email: str, creds: Credentials) -> User:
        logger.debug("AuthService._upsert_user — email: %s", email)
        try:
            def _db_write():
                user, created = self._user_repo.get_or_create(email)
                action = "created" if created else "updated"
                logger.info("AuthService._upsert_user — %s user record: %s", action, email)

                access_enc = encrypt_token(creds.token)
                refresh_enc = encrypt_token(creds.refresh_token) if creds.refresh_token else None
                return self._user_repo.update_tokens(
                    user, access_enc, refresh_enc, creds.expiry
                )

            user = await asyncio.to_thread(_db_write)
            logger.info("AuthService._upsert_user — tokens stored for: %s", email)
            return user
        except Exception as e:
            logger.error("AuthService._upsert_user — DB error: %s", str(e))
            raise UserSessionError("Failed to store user session")

    async def _revoke_token(self, user: User) -> None:
        if not user.access_token_enc:
            return
        try:
            import requests as req
            token = decrypt_token(user.access_token_enc)
            logger.debug("AuthService._revoke_token — revoking for user: %s", user.email)
            resp = await asyncio.to_thread(
                lambda: req.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            )
            logger.info("AuthService._revoke_token — Google response: %s", resp.status_code)
        except Exception as e:
            # Revocation failure is non-fatal — log and continue
            logger.warning("AuthService._revoke_token — failed (continuing): %s", str(e))
