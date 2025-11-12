"""Timeline endpoint for entity mentions over time."""
from __future__ import annotations
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from collections import Counter
from datetime import datetime
from typing import List, Dict
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

router = APIRouter(prefix="/api", tags=["timeline"])


def summarize_timeline(timeline: List[Dict]) -> str:
    """
    Generate a summary of timeline data.
    
    Args:
        timeline: List of {year, count} dicts
        
    Returns:
        Summary string
    """
    if not timeline:
        return "No timeline data available."
    
    peak = max(timeline, key=lambda x: x.get("count", 0))
    total = sum(p.get("count", 0) for p in timeline)
    years_span = len(timeline)
    
    return f"Mentions peaked in {peak.get('year')} with {peak.get('count')} articles. Total: {total} mentions across {years_span} year{'s' if years_span != 1 else ''}."


@router.get("/timeline")
async def timeline(request: Request, q: str = Query(..., description="Search term to track over time")):
    """
    Get timeline of mentions for a search term across tracked articles.
    
    Args:
        q: Search term to find in article text
        
    Returns:
        JSON with 'ok' flag, 'term', and 'timeline' (list of {year, count})
    """
    try:
        # Get session ID from request
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        articles = list_articles(sid, limit=100)
        
        # Find articles containing the search term
        hits = []
        q_lower = q.lower()
        
        for art in articles:
            # Search in summary, snippet, or full_text
            text = art.get("summary") or art.get("snippet") or art.get("full_text") or ""
            if not text or q_lower not in text.lower():
                continue
            
            # Extract year from date
            dt = art.get("date")
            if dt:
                try:
                    # Try various date formats
                    year = None
                    if isinstance(dt, str):
                        # Try YYYY-MM-DD
                        try:
                            year = datetime.strptime(dt, "%Y-%m-%d").year
                        except ValueError:
                            # Try YYYY
                            try:
                                year = int(dt[:4])
                            except ValueError:
                                pass
                    elif isinstance(dt, (int, float)):
                        # Already a year or timestamp
                        if dt > 1900 and dt < 2100:
                            year = int(dt)
                        elif dt > 1000000000:  # Unix timestamp
                            year = datetime.fromtimestamp(dt).year
                    
                    if year:
                        hits.append(str(year))
                except Exception:
                    continue
        
        # Count mentions by year
        counter = Counter(hits)
        points = [{"year": k, "count": v} for k, v in sorted(counter.items())]
        
        return JSONResponse(content={
            "ok": True,
            "term": q,
            "timeline": points
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "term": q, "timeline": []}
        )


@router.get("/timeline/hits")
async def timeline_hits(request: Request, q: str = Query(..., description="Search term"), year: str = Query(..., description="Year to filter by")):
    """
    Get articles matching a search term in a specific year.
    
    Args:
        q: Search term to find in article text
        year: Year to filter articles (e.g., "1926")
        
    Returns:
        JSON with 'ok' flag and 'results' (list of matching articles)
    """
    try:
        # Get session ID from request
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        articles = list_articles(sid, limit=100)
        
        matched = []
        q_lower = q.lower()
        
        for art in articles:
            # Search in summary, snippet, or full_text
            text = art.get("summary") or art.get("snippet") or art.get("full_text") or ""
            if not text or q_lower not in text.lower():
                continue
            
            # Check if date matches year
            dt = art.get("date")
            if dt:
                dt_str = str(dt)
                if dt_str.startswith(year):
                    matched.append({
                        "title": art.get("title", "Untitled"),
                        "date": art.get("date"),
                        "source": art.get("source"),
                        "trove_id": art.get("trove_id"),
                        "snippet": art.get("snippet") or art.get("summary") or "",
                        "url": art.get("url")
                    })
        
        return JSONResponse(content={
            "ok": True,
            "term": q,
            "year": year,
            "results": matched
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "term": q, "year": year, "results": []}
        )


@router.get("/timeline/compare")
async def compare_timeline(request: Request, q: str = Query(..., description="Comma-separated terms to compare")):
    """
    Compare timeline mentions for multiple terms.
    
    Args:
        q: Comma-separated list of terms (e.g., "Gallipoli,Churchill")
        
    Returns:
        JSON with 'ok' flag, 'years' list, and 'datasets' (one per term)
    """
    try:
        # Get session ID from request
        headers_dict = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"
        user_agent = headers_dict.get("user-agent", "")
        sid = sid_from(headers_dict, client_host, user_agent)
        
        # Get all articles for this session
        articles = list_articles(sid, limit=100)
        
        # Parse terms
        terms = [t.strip() for t in q.split(",") if t.strip()]
        if not terms:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "At least one term required", "years": [], "datasets": []}
            )
        
        # Count mentions by year for each term
        year_term_count = {}
        
        for art in articles:
            text = art.get("summary") or art.get("snippet") or art.get("full_text") or ""
            if not text:
                continue
            
            date = art.get("date", "")
            if not date:
                continue
            
            # Extract year
            try:
                year = None
                if isinstance(date, str):
                    # Try YYYY-MM-DD
                    try:
                        year = datetime.strptime(date, "%Y-%m-%d").year
                    except ValueError:
                        # Try YYYY
                        try:
                            year = int(date[:4])
                        except ValueError:
                            pass
                elif isinstance(date, (int, float)):
                    if date > 1900 and date < 2100:
                        year = int(date)
                    elif date > 1000000000:  # Unix timestamp
                        year = datetime.fromtimestamp(date).year
                
                if not year:
                    continue
                
                # Check each term
                for term in terms:
                    if term.lower() in text.lower():
                        if term not in year_term_count:
                            year_term_count[term] = {}
                        if year not in year_term_count[term]:
                            year_term_count[term][year] = 0
                        year_term_count[term][year] += 1
            except Exception:
                continue
        
        # Get all years across all terms
        all_years = sorted(set(yr for counts in year_term_count.values() for yr in counts))
        
        # Build datasets
        datasets = []
        colors = [
            "rgba(102, 153, 204, 0.8)",  # Blue
            "rgba(221, 85, 85, 0.8)",    # Red
            "rgba(85, 221, 85, 0.8)",    # Green
            "rgba(221, 221, 85, 0.8)",   # Yellow
            "rgba(221, 85, 221, 0.8)",   # Magenta
            "rgba(85, 221, 221, 0.8)",   # Cyan
        ]
        
        for idx, term in enumerate(terms):
            data = [year_term_count.get(term, {}).get(yr, 0) for yr in all_years]
            datasets.append({
                "label": term,
                "data": data,
                "borderColor": colors[idx % len(colors)],
                "backgroundColor": colors[idx % len(colors)].replace("0.8", "0.3"),
                "borderWidth": 2
            })
        
        return JSONResponse(content={
            "ok": True,
            "terms": terms,
            "years": all_years,
            "datasets": datasets
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "terms": [], "years": [], "datasets": []}
        )

