from cryptography.fernet import Fernet, InvalidToken
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


def _fernet() -> Fernet:
    try:
        return Fernet(settings.encryption_key.encode())
    except Exception as e:
        logger.error("Failed to initialise Fernet — check ENCRYPTION_KEY in .env: %s", str(e))
        raise


def encrypt_token(token: str) -> str:
    logger.debug("Encrypting token (length: %d chars)", len(token))
    try:
        encrypted = _fernet().encrypt(token.encode()).decode()
        logger.debug("Token encrypted successfully")
        return encrypted
    except Exception as e:
        logger.error("Token encryption failed: %s", str(e))
        raise


def decrypt_token(token_enc: str) -> str:
    logger.debug("Decrypting stored token")
    try:
        decrypted = _fernet().decrypt(token_enc.encode()).decode()
        logger.debug("Token decrypted successfully")
        return decrypted
    except InvalidToken:
        logger.error("Token decryption failed — token is invalid or key has changed")
        raise
    except Exception as e:
        logger.error("Unexpected error during token decryption: %s", str(e))
        raise
