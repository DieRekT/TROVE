"""Entity extraction endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

# Add parent directory to path to import context_store
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
try:
    from app.context_store import sid_from, list_articles
except ImportError:
    # Fallback if context_store is in a different location
    try:
        from context_store import sid_from, list_articles
    except ImportError:
        # Stub functions if context_store not available
        def sid_from(headers: dict, ip: str, ua: str) -> str:
            return "default"
        def list_articles(sid: str, limit: int = 50) -> list:
            return []

from ..nlp.entity_extract import extract_entities

router = APIRouter(prefix="/api", tags=["entities"])


@router.get("/entities")
async def get_entities(request: Request):
    """
    Extract entities from all tracked articles in the current session.
    
    Returns:
        JSON with 'ok' flag and 'entities' list (deduplicated, with counts)
    """
    try:
        # Get session ID from request
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        articles = list_articles(sid, limit=100)
        
        # Extract entities from all articles
        entity_map = {}
        
        for art in articles:
            # Try summary first, then snippet, then full_text
            text = art.get("summary") or art.get("snippet") or art.get("full_text") or ""
            if not text:
                continue
            
            # Extract entities from this article
            entities = extract_entities(text)
            
            # Aggregate by (text, label) key
            for ent in entities:
                key = (ent["text"], ent["label"])
                if key not in entity_map:
                    entity_map[key] = {
                        "text": ent["text"],
                        "label": ent["label"],
                        "link": ent.get("link"),
                        "count": 1
                    }
                else:
                    entity_map[key]["count"] += 1
                    # Keep link if we have one and the existing one is None
                    if ent.get("link") and not entity_map[key].get("link"):
                        entity_map[key]["link"] = ent.get("link")
        
        # Convert to list and sort by count (descending)
        entities_list = list(entity_map.values())
        entities_list.sort(key=lambda x: x["count"], reverse=True)
        
        return JSONResponse(content={
            "ok": True,
            "entities": entities_list
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )

