"""Structured analysis engine for entity extraction and summarization over filtered article sets."""
from __future__ import annotations
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime
import re
import logging
import sys
from pathlib import Path

# Add parent directory to path to import context_store
# Try multiple import paths
try:
    from app.context_store import sid_from, list_articles
except ImportError:
    try:
        # Try relative import from parent
        import sys
        parent_path = str(Path(__file__).parent.parent.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        from app.context_store import sid_from, list_articles
    except ImportError:
        try:
            from context_store import sid_from, list_articles
        except ImportError:
            # Stub functions if context_store not available
            def sid_from(headers: dict, ip: str, ua: str) -> str:
                return "default"
            def list_articles(sid: str, limit: int = 50) -> list:
                return []

# Import entity extraction
try:
    from app.nlp.entity_extract import extract_entities
except ImportError:
    def extract_entities(text: str) -> List[Dict]:
        return []

# Import summarization
try:
    from app.archive_detective.summarize import summarize_text
except ImportError:
    def summarize_text(text: str, use_llm: bool = True) -> dict:
        return {"bullets": [], "summary": ""}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    """Request model for structured analysis."""
    keywords: Optional[str] = None  # Comma-separated keywords to filter articles
    date_from: Optional[str] = None  # YYYY-MM-DD or YYYY
    date_to: Optional[str] = None  # YYYY-MM-DD or YYYY
    entity_types: Optional[List[str]] = None  # Filter entity types: PERSON, ORG, GPE, LOC, EVENT, etc.
    max_articles: Optional[int] = 100  # Maximum articles to process
    use_llm: Optional[bool] = True  # Use LLM for summarization if available


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass
    
    # Try YYYY
    try:
        if len(date_str) == 4 and date_str.isdigit():
            return datetime(int(date_str), 1, 1)
    except ValueError:
        pass
    
    return None


def _date_in_range(article_date: Optional[str], date_from: Optional[datetime], date_to: Optional[datetime]) -> bool:
    """Check if article date falls within range."""
    if not article_date:
        return date_from is None and date_to is None  # Include undated if no range specified
    
    article_dt = _parse_date(article_date)
    if not article_dt:
        return date_from is None and date_to is None
    
    if date_from and article_dt < date_from:
        return False
    if date_to and article_dt > date_to:
        return False
    
    return True


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """Check if text matches any keyword (case-insensitive)."""
    if not keywords:
        return True
    
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def _filter_articles(
    articles: List[Dict[str, Any]],
    keywords: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    max_articles: int = 100
) -> List[Dict[str, Any]]:
    """Filter articles by keywords and date range."""
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []
    date_from_dt = _parse_date(date_from)
    date_to_dt = _parse_date(date_to)
    
    filtered = []
    for article in articles:
        # Check date range
        if not _date_in_range(article.get("date"), date_from_dt, date_to_dt):
            continue
        
        # Check keywords
        text_fields = [
            article.get("title", ""),
            article.get("snippet", ""),
            article.get("full_text", ""),
            article.get("summary", "")
        ]
        article_text = " ".join(filter(None, text_fields))
        
        if keyword_list and not _matches_keywords(article_text, keyword_list):
            continue
        
        filtered.append(article)
        
        if len(filtered) >= max_articles:
            break
    
    return filtered


@router.post("/extract-entities")
async def extract_entities_from_articles(
    request: Request,
    req: AnalysisRequest
):
    """
    Extract entities from filtered article sets.
    
    Example: Extract all people mentioned in 1915 Gallipoli articles
    """
    try:
        # Get session ID
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        all_articles = list_articles(sid, limit=1000)
        
        # Filter articles
        filtered_articles = _filter_articles(
            all_articles,
            keywords=req.keywords,
            date_from=req.date_from,
            date_to=req.date_to,
            max_articles=req.max_articles or 100
        )
        
        if not filtered_articles:
            return JSONResponse(content={
                "ok": True,
                "message": "No articles found matching the criteria",
                "articles_processed": 0,
                "entities": []
            })
        
        # Extract entities from all filtered articles
        entity_map: Dict[tuple, Dict[str, Any]] = {}  # (name, label) -> entity dict
        
        for article in filtered_articles:
            # Combine all text fields
            text_fields = [
                article.get("title", ""),
                article.get("snippet", ""),
                article.get("full_text", ""),
                article.get("summary", "")
            ]
            article_text = " ".join(filter(None, text_fields))
            
            if not article_text:
                continue
            
            # Extract entities
            entities = extract_entities(article_text)
            
            # Aggregate entities
            for ent in entities:
                key = (ent["text"].lower(), ent["label"])
                if key not in entity_map:
                    entity_map[key] = {
                        "text": ent["text"],
                        "label": ent["label"],
                        "link": ent.get("link"),
                        "count": 1,
                        "articles": [article.get("trove_id", "unknown")]
                    }
                else:
                    entity_map[key]["count"] += 1
                    if article.get("trove_id") and article.get("trove_id") not in entity_map[key]["articles"]:
                        entity_map[key]["articles"].append(article.get("trove_id"))
        
        # Filter by entity types if specified
        entities_list = list(entity_map.values())
        if req.entity_types:
            entities_list = [e for e in entities_list if e["label"] in req.entity_types]
        
        # Sort by count (most mentioned first)
        entities_list.sort(key=lambda x: x["count"], reverse=True)
        
        return JSONResponse(content={
            "ok": True,
            "articles_processed": len(filtered_articles),
            "entities": entities_list,
            "filters": {
                "keywords": req.keywords,
                "date_from": req.date_from,
                "date_to": req.date_to,
                "entity_types": req.entity_types
            }
        })
    
    except Exception as e:
        logger.exception(f"Entity extraction failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.post("/summarize")
async def summarize_articles(
    request: Request,
    req: AnalysisRequest
):
    """
    Summarize filtered article sets.
    
    Example: Summarise Australian coverage of WWII between 1939–1945
    """
    try:
        # Get session ID
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        all_articles = list_articles(sid, limit=1000)
        
        # Filter articles
        filtered_articles = _filter_articles(
            all_articles,
            keywords=req.keywords,
            date_from=req.date_from,
            date_to=req.date_to,
            max_articles=req.max_articles or 100
        )
        
        if not filtered_articles:
            return JSONResponse(content={
                "ok": True,
                "message": "No articles found matching the criteria",
                "articles_processed": 0,
                "summary": "",
                "bullets": []
            })
        
        # Combine article text for summarization
        combined_text_parts = []
        article_metadata = []
        
        for article in filtered_articles:
            # Get best available text
            text = article.get("full_text") or article.get("summary") or article.get("snippet", "")
            if not text:
                continue
            
            # Add metadata context
            title = article.get("title", "Untitled")
            date = article.get("date", "")
            source = article.get("source", "")
            
            # Format: [Title (Date, Source)] Text...
            if date or source:
                header = f"[{title}"
                if date:
                    header += f" ({date}"
                    if source:
                        header += f", {source}"
                    header += ")"
                elif source:
                    header += f" ({source})"
                header += "] "
                combined_text_parts.append(header + text[:2000])  # Limit per article
            else:
                combined_text_parts.append(f"[{title}] " + text[:2000])
            
            article_metadata.append({
                "trove_id": article.get("trove_id"),
                "title": title,
                "date": date,
                "source": source
            })
        
        if not combined_text_parts:
            return JSONResponse(content={
                "ok": True,
                "message": "No text content found in filtered articles",
                "articles_processed": len(filtered_articles),
                "summary": "",
                "bullets": []
            })
        
        # Combine all text (limit total length)
        combined_text = "\n\n".join(combined_text_parts)
        if len(combined_text) > 15000:
            combined_text = combined_text[:15000] + "..."
        
        # Generate summary
        summary_result = summarize_text(combined_text, use_llm=req.use_llm if req.use_llm is not None else True)
        
        return JSONResponse(content={
            "ok": True,
            "articles_processed": len(filtered_articles),
            "summary": summary_result.get("summary", ""),
            "bullets": summary_result.get("bullets", []),
            "article_count": len(article_metadata),
            "filters": {
                "keywords": req.keywords,
                "date_from": req.date_from,
                "date_to": req.date_to
            },
            "articles": article_metadata[:20]  # Include first 20 for reference
        })
    
    except Exception as e:
        logger.exception(f"Summarization failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={
        "ok": True,
        "entity_extraction": extract_entities is not None,
        "summarization": summarize_text is not None
    })

