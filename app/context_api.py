"""FastAPI router for context store API endpoints."""

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from .context_store import upsert_item, list_articles, clear_session, set_pinned, pack_for_prompt, sid_from

router = APIRouter()


class ArticleIn(BaseModel):
    """Article tracking payload."""
    trove_id: str = Field(..., description="Stable article ID")
    title: str
    date: str = ""
    source: str = ""
    url: str = ""
    snippet: str = ""


@router.get("/api/context")
async def get_context(request: Request):
    """Get all articles for current session."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    return {"ok": True, "sid": sid, "items": list_articles(sid)}


@router.post("/api/context/track")
async def post_track(request: Request, a: ArticleIn):
    """Track an article (add to context)."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    try:
        return upsert_item(sid, a.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/context/pin/{trove_id}")
async def pin(request: Request, trove_id: str):
    """Pin an article."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    set_pinned(sid, trove_id, True)
    return {"ok": True}


@router.post("/api/context/unpin/{trove_id}")
async def unpin(request: Request, trove_id: str):
    """Unpin an article."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    set_pinned(sid, trove_id, False)
    return {"ok": True}


@router.delete("/api/context")
async def clear(request: Request):
    """Clear all articles for current session."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    clear_session(sid)
    return {"ok": True}


@router.get("/api/context/pack")
async def get_pack(request: Request, max_chars: int = Query(3500, ge=100, le=10000)):
    """Get packed context for prompt (with character limit)."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    packed = pack_for_prompt(sid, max_chars=max_chars)
    return {"ok": True, "sid": sid, **packed}

