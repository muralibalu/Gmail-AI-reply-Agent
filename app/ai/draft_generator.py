from typing import List
from openai import AsyncOpenAI
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        logger.info("Initialising AsyncOpenAI client — base_url: %s", settings.openai_base_url)
        try:
            _client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            logger.debug("AsyncOpenAI client initialised successfully")
        except Exception as e:
            logger.error("Failed to initialise AsyncOpenAI client: %s", str(e))
            raise
    return _client


async def generate_draft(
    sender: str,
    subject: str,
    original_body: str,
    tone: str = "formal",
    sent_email_samples: List[str] = None,
    instructions: str = "",
) -> str:
    """Async draft generation via OpenRouter — does not block the event loop."""
    logger.info(
        "Generating draft — from: %s | subject: %s | tone: %s | has_instructions: %s",
        sender, subject, tone, bool(instructions),
    )

    style_context = ""
    if sent_email_samples:
        sample_count = min(len(sent_email_samples), 5)
        logger.debug("Using %d sent email(s) as style context", sample_count)
        samples = "\n---\n".join(sent_email_samples[:sample_count])
        style_context = f"""
Here are some of the user's recent sent emails to learn their writing style:
{samples}

Match the user's tone, phrasing, and style in the reply.
"""
    else:
        logger.debug("No sent email samples — using tone-only prompt")

    tone_instructions = {
        "formal":   "Write in a professional and formal tone.",
        "concise":  "Write a brief and to-the-point reply.",
        "friendly": "Write in a warm and friendly tone.",
    }.get(tone, "Write in a professional tone.")

    system_prompt = f"""You are an AI email assistant that drafts replies on behalf of the user.
{tone_instructions}
{style_context}
Only return the reply body — no subject line, no greeting like "Dear Claude", just the reply content."""

    instructions_section = ""
    if instructions.strip():
        instructions_section = f"\nUser instructions for this reply:\n{instructions.strip()}\n"
        logger.debug("Injecting user instructions: %s", instructions.strip())

    user_prompt = f"""Draft a reply to this email:

From: {sender}
Subject: {subject}

{original_body}
{instructions_section}"""

    client = _get_client()
    logger.debug("Sending async request to model — base_url: %s", settings.openai_base_url)

    try:
        response = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        draft = response.choices[0].message.content.strip()
        logger.info("Draft generated — subject: %s | length: %d chars", subject, len(draft))
        logger.debug("Token usage — prompt: %d | completion: %d",
                     response.usage.prompt_tokens, response.usage.completion_tokens)
        return draft
    except Exception as e:
        logger.error("Async API call failed — base_url: %s | subject: %s | error: %s",
                     settings.openai_base_url, subject, str(e))
        raise
