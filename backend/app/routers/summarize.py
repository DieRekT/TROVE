from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api", tags=["summarize"])


class Item(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None


class SummarizeReq(BaseModel):
    items: List[Item]


@router.post("/summarize")
async def summarize(req: SummarizeReq):
    """Lightweight local summarizer (no LLM): extract dates/names, compress lines."""
    bullets = []
    for it in req.items[:8]:
        base = (it.date or "")
        text = (it.snippet or it.title or "").strip()
        if len(text) > 160:
            text = text[:157] + "…"
        bullets.append(f"{base}: {text}" if base else text)
    
    # Return ≤800 chars
    total = " • ".join(bullets)
    if len(total) > 800:
        total = total[:797] + "…"
    
    return {"bullets": total}

