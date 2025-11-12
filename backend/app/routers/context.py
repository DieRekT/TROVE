from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("")
async def get_context():
    """Get tracked articles (stub - returns empty for now)."""
    return JSONResponse(content={"ok": True, "items": []})


@router.post("/track")
async def track_article():
    """Track an article (stub)."""
    return JSONResponse(content={"ok": True})


@router.post("/pin/{article_id}")
async def pin_article(article_id: str):
    """Pin an article (stub)."""
    return JSONResponse(content={"ok": True})


@router.post("/unpin/{article_id}")
async def unpin_article(article_id: str):
    """Unpin an article (stub)."""
    return JSONResponse(content={"ok": True})


@router.get("/stats")
async def context_stats():
    """Get context statistics (stub)."""
    return JSONResponse(content={"ok": True, "total": 0, "pinned": 0})


@router.get("/pack")
async def pack_context():
    """Get formatted context for AI (stub)."""
    return JSONResponse(content={"ok": True, "context": "", "items": []})


@router.delete("")
async def clear_context():
    """Clear all tracked articles (stub)."""
    return JSONResponse(content={"ok": True})

