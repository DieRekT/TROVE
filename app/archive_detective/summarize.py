from __future__ import annotations

import re
from typing import Any

from .config import AI_MODEL_ROUTER, OPENAI_API_KEY


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
            prompt = (
                "Summarize as tight bullet points for a property-history researcher.\n"
                "Include dates, names, places, and actions. 5–8 bullets, max 800 chars total."
            )
            resp = cli.chat.completions.create(
                model=AI_MODEL_ROUTER,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": "You compress text into factual bullets with dates and names.",
                    },
                    {"role": "user", "content": prompt + "\n\nTEXT:\n" + text[:8000]},
                ],
            )
            out = (resp.choices[0].message.content or "").strip()
            bullets = [("• " + b.strip("-• \n")) for b in out.split("\n") if b.strip()]
            return {"bullets": bullets[:10], "summary": "\n".join(bullets[:10])}
        except Exception:
            pass

    # fallback (free)
    bullets = _fallback_bullets(text, max_points=7)
    return {"bullets": bullets, "summary": "\n".join(bullets)}
