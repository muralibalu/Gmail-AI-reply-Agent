import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Format includes: timestamp | level | filename:line_number | message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger that writes to:
      - logs/draftly.log  (rotating, max 5 MB x 3 backups)
      - console (stdout)
    Each log line shows filename and line number.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured — don't add duplicate handlers

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── File handler (rotating) ──────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "draftly.log"),
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ── Console handler ──────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
