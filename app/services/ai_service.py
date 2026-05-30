"""
AIService — singleton service wrapping the AsyncOpenAI client.

Responsibilities:
  - Single AsyncOpenAI client instance (not recreated per request)
  - Translates AI errors into domain exceptions
  - Decouples business logic from the specific AI provider
"""
from app.ai.draft_generator import generate_draft
from app.exceptions import AIGenerationError
from app.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """
    Stateless service — safe to instantiate per request or use as a singleton.
    All state lives in the underlying AsyncOpenAI client (in draft_generator).
    """

    async def generate_draft(
        self,
        sender: str,
        subject: str,
        original_body: str,
        tone: str = "formal",
        sent_email_samples: list[str] | None = None,
        instructions: str = "",
    ) -> str:
        logger.info("AIService.generate_draft — subject: %s | tone: %s | has_instructions: %s",
                    subject, tone, bool(instructions))
        try:
            draft = await generate_draft(
                sender=sender,
                subject=subject,
                original_body=original_body,
                tone=tone,
                sent_email_samples=sent_email_samples or [],
                instructions=instructions,
            )
            logger.info("AIService.generate_draft succeeded — length: %d chars", len(draft))
            return draft
        except Exception as e:
            logger.error("AIService.generate_draft failed — subject: %s | error: %s",
                         subject, str(e))
            raise AIGenerationError(f"AI draft generation failed: {str(e)}")
