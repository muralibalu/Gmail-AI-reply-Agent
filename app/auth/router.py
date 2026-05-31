"""
Auth router — thin HTTP layer only.

All OAuth2 business logic lives in AuthService.
This file only handles: HTTP routing, request/response shapes,
exception-to-HTTP mapping, and redirects.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.services.auth_service import AuthService
from app.dependencies import get_auth_service
from app.exceptions import DraftlyException
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(auth_service: AuthService = Depends(get_auth_service)):
    """Initiate OAuth2 login — redirect user to Google consent screen."""
    try:
        auth_url, state = auth_service.build_authorization_url()
        logger.info("Login initiated — redirecting to Google consent screen")
        return RedirectResponse(auth_url)
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in /auth/login: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Handle Google OAuth2 callback — exchange code, store tokens, redirect to frontend."""
    try:
        email = await auth_service.handle_callback(code=code, state=state)
        logger.info("OAuth2 callback complete — user: %s", email)
        return RedirectResponse(f"http://localhost:5173/?email={email}")
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in /auth/callback: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/logout")
async def logout(
    user_email: str,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Revoke Gmail access and clear stored tokens."""
    try:
        await auth_service.logout(user_email)
        logger.info("Logout complete — user: %s", user_email)
        return {"message": "Logged out and tokens revoked"}
    except DraftlyException as e:
        raise e.to_http()
    except Exception as e:
        logger.error("Unexpected error in /auth/logout: %s", str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Logout failed")
