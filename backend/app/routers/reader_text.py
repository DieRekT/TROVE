from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from ..services.trove_client import TroveClient
from ..services.extract_fulltext import fetch_url, trafilatura_extract, readability_extract

router = APIRouter(prefix="/api/reader", tags=["reader"])


@router.get("/text", response_class=JSONResponse)
async def get_reader_text(id: str = Query(...), url: str | None = None):
    """Get full article text with fallback chain: Trove articleText → scrape → snippet."""
    # 1) Trove articleText
    try:
        trove = TroveClient()
        payload = await trove.search(q=id, n=1, reclevel="full", include="articleText,links")
        hits = TroveClient.extract_hits(payload)
    except Exception:
        hits = []
    
    if hits:
        rec = hits[0]
        at = (rec.get("articleText") or "").strip()
        if at and len(at) > 100:
            return {"id": id, "source": "trove_articleText", "text": at}
    
    # 2) Try provided URL (or resolver) with trafilatura → readability
    u = url or (hits and TroveClient.article_url(hits[0])) or None
    if u:
        try:
            html = await fetch_url(u)
            if html:
                txt = trafilatura_extract(html) or readability_extract(html)
                if txt and len(txt) > 120:
                    return {"id": id, "source": "scrape_fallback", "text": txt, "url": u}
        except Exception as e:
            # fall through to snippet
            pass
    
    # 3) Snippet fallback (last resort)
    if hits:
        rec = hits[0]
        snip = (rec.get("snippet") or "").strip()
        if snip:
            return {"id": id, "source": "snippet", "text": snip}
    
    raise HTTPException(status_code=404, detail="No text available")

