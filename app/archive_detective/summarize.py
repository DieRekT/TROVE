from __future__ import annotations

import os
import re
from typing import Any

from .config import AI_MODEL_ROUTER, OPENAI_API_KEY

# Import registry and telemetry
try:
    from app.prompts.registry import get_summarize_prompts
    from app.prompts.telemetry import log_summarize
except ImportError:
    # Fallback: try backend path if app.prompts doesn't exist
    try:
        from backend.app.prompts.registry import get_summarize_prompts
        from backend.app.prompts.telemetry import log_summarize
    except ImportError:
        # Last resort: create stub functions
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Prompt registry not found, using fallback")
        def get_summarize_prompts(version: str | None = None) -> tuple[str, str]:
            return ("Summarize system prompt", "Summarize user prompt: {body}")
        def log_summarize(*args, **kwargs) -> None:
            pass

# Load prompts from registry
SUMMARIZE_SYSTEM, SUMMARIZE_USER = get_summarize_prompts()
PROMPT_VERSION = os.getenv("PROMPTS_SUMMARIZE_VERSION", "v2")


def _fallback_bullets(text: str, max_points: int = 7) -> list[str]:
    # ultra-light extractive fallback: split sentences, pick diverse informative ones
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s.strip() for s in sents if 40 <= len(s) <= 300]  # avoid very short/long

    # very simple scoring: prefer sentences with dates, numbers, names-like words
    def score(s: str) -> int:
        return sum(
            [
                3 if re.search(r"\b(18|19|20)\d{2}\b", s) else 0,
                2 if re.search(r"\b[A-Z][a-z]{2,}\b.*\b[A-Z][a-z]{2,}\b", s) else 0,
                1 if re.search(r"\d", s) else 0,
                1 if len(s) > 120 else 0,
            ]
        )

    ranked = sorted(sents, key=score, reverse=True)[:max_points]
    return ["• " + r for r in ranked]


def summarize_text(text: str, use_llm: bool = True) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"bullets": [], "summary": ""}

    if use_llm and OPENAI_API_KEY:
        try:
            from openai import OpenAI

            cli = OpenAI(api_key=OPENAI_API_KEY)
            # Build user prompt from template
            user_prompt = SUMMARIZE_USER.format(body=text[:8000])
            resp = cli.chat.completions.create(
                model=AI_MODEL_ROUTER,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            )
            out = (resp.choices[0].message.content or "").strip()
            bullets = [("• " + b.strip("-• \n")) for b in out.split("\n") if b.strip()]
            result = {"bullets": bullets[:10], "summary": "\n".join(bullets[:10])}
            
            # Log telemetry
            try:
                has_dates = any(re.search(r"\b(18|19|20)\d{2}\b", bullet) for bullet in bullets)
                log_summarize(PROMPT_VERSION, len(text), len(result["summary"]), has_dates)
            except Exception:
                pass  # Don't fail on telemetry errors
            
            return result
        except Exception:
            pass

    # fallback (free)
    bullets = _fallback_bullets(text, max_points=7)
    return {"bullets": bullets, "summary": "\n".join(bullets)}
