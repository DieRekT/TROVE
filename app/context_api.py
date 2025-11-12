"""FastAPI router for context store API endpoints."""

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from .context_store import upsert_item, list_articles, clear_session, clear_tracked_only, set_pinned, pack_for_prompt, sid_from, move_pinned_article

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
async def clear(request: Request, pinned_only: bool = Query(False, description="If true, only clear pinned articles. If false, clear all.")):
    """Clear articles for current session. By default clears all, or only tracked (non-pinned) if pinned_only=False."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    if pinned_only:
        # Clear only pinned articles (unusual, but available)
        from .context_store import _connect, ensure_db
        ensure_db()
        with _connect() as c:
            c.execute("DELETE FROM articles WHERE sid=? AND pinned=1", (sid,))
    else:
        clear_session(sid)
    return {"ok": True}


@router.delete("/api/context/tracked")
async def clear_tracked(request: Request):
    """Clear only tracked (non-pinned) articles, keeping pinned articles."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    clear_tracked_only(sid)
    return {"ok": True}


@router.post("/api/context/move/{trove_id}")
async def move_article(request: Request, trove_id: str, direction: str = Query(..., pattern="^(up|down)$")):
    """Move a pinned article up or down in the order."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    moved = move_pinned_article(sid, trove_id, direction)
    if not moved:
        raise HTTPException(status_code=400, detail="Could not move article")
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


@router.get("/api/context/stats")
async def get_stats(request: Request):
    """Get context statistics (pinned count, total count)."""
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    articles = list_articles(sid)
    # pinned is stored as INTEGER (0 or 1) in the database
    pinned_count = sum(1 for a in articles if a.get("pinned", 0) == 1)
    total_count = len(articles)
    tracked_count = total_count - pinned_count
    return {
        "ok": True,
        "pinned": pinned_count,
        "tracked": tracked_count,
        "total": total_count,
        "sid": sid
    }


@router.get("/api/context/export")
async def export_context(request: Request, format: str = Query("json", pattern="^(json|csv)$")):
    """Export tracked articles as JSON or CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    articles = list_articles(sid)
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["trove_id", "title", "date", "source", "url", "snippet", "pinned"])
        writer.writeheader()
        for article in articles:
            writer.writerow({
                "trove_id": article.get("trove_id", ""),
                "title": article.get("title", ""),
                "date": article.get("date", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "snippet": article.get("snippet", ""),
                "pinned": "Yes" if article.get("pinned", 0) == 1 else "No"
            })
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tracked-articles.csv"}
        )
    else:
        # JSON format
        return {
            "ok": True,
            "sid": sid,
            "count": len(articles),
            "items": articles
        }

