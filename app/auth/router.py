from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from app.database import get_db
from app.models import User
from app.security import encrypt_token, decrypt_token
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

_flow_store: dict[str, Flow] = {}


def _build_flow() -> Flow:
    try:
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
    except Exception as e:
        logger.error("Failed to build OAuth2 flow: %s", str(e))
        raise


@router.get("/login")
def login():
    """Redirect user to Google OAuth2 consent screen."""
    logger.info("OAuth2 login initiated — building consent URL")
    try:
        flow = _build_flow()
        auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
        _flow_store[state] = flow
        logger.debug("Flow stored — state: %s | pending flows: %d", state, len(_flow_store))
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.error("Login redirect failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to initiate OAuth2 login")


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    """Handle OAuth2 callback — exchange code for tokens and store encrypted."""
    logger.info("OAuth2 callback received — state: %s", state)

    flow = _flow_store.pop(state, None)
    if not flow:
        logger.error("No flow found for state=%s — CSRF or expired session", state)
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth2 state")

    try:
        flow.fetch_token(code=code)
        creds: Credentials = flow.credentials
        logger.debug("Token exchange successful — expiry: %s", creds.expiry)
    except Exception as e:
        logger.error("Token exchange failed: %s", str(e))
        raise HTTPException(status_code=400, detail="OAuth2 token exchange failed")

    try:
        import google.auth.transport.requests
        session = google.auth.transport.requests.AuthorizedSession(creds)
        userinfo = session.get("https://www.googleapis.com/oauth2/v2/userinfo").json()
        email = userinfo["email"]
        logger.info("Verified identity — email: %s | verified: %s",
                    email, userinfo.get("verified_email"))
    except Exception as e:
        logger.error("Userinfo fetch failed: %s", str(e))
        raise HTTPException(status_code=400, detail="Could not retrieve user info from Google")

    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.info("New user — creating record for: %s", email)
            user = User(email=email)
            db.add(user)
        else:
            logger.info("Existing user — refreshing tokens for: %s", email)

        user.access_token_enc = encrypt_token(creds.token)
        user.refresh_token_enc = (
            encrypt_token(creds.refresh_token)
            if creds.refresh_token else user.refresh_token_enc
        )
        user.token_expiry = creds.expiry
        db.commit()
        logger.debug("Tokens committed to DB for user: %s", email)
    except Exception as e:
        logger.error("DB error saving tokens for user %s: %s", email, str(e))
        raise HTTPException(status_code=500, detail="Failed to store user session")

    logger.info("Auth complete for: %s — redirecting to frontend", email)
    return RedirectResponse(f"http://localhost:5173/?email={email}")


@router.post("/logout")
def logout(user_email: str, db: Session = Depends(get_db)):
    """Revoke Gmail access and clear stored tokens."""
    logger.info("Logout requested for user: %s", user_email)

    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            logger.warning("Logout failed — user not found: %s", user_email)
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB error fetching user %s for logout: %s", user_email, str(e))
        raise HTTPException(status_code=500, detail="Database error")

    if user.access_token_enc:
        try:
            import requests as req
            access_token = decrypt_token(user.access_token_enc)
            logger.debug("Revoking Google access token for user: %s", user_email)
            resp = req.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            logger.info("Google revocation response: %s for user: %s",
                        resp.status_code, user_email)
        except Exception as e:
            logger.warning("Token revocation failed (continuing logout): %s", str(e))

    try:
        user.access_token_enc = None
        user.refresh_token_enc = None
        user.token_expiry = None
        db.commit()
        logger.info("Tokens cleared for user: %s", user_email)
    except Exception as e:
        logger.error("DB error clearing tokens for user %s: %s", user_email, str(e))
        raise HTTPException(status_code=500, detail="Failed to clear session")

    return {"message": "Logged out and tokens revoked"}
