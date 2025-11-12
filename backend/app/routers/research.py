from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import os
import asyncio
import logging
import uuid
from typing import Optional

# Import from root-level app modules
import sys
from pathlib import Path
root_path = Path(__file__).parent.parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

try:
    from app.archive_detective.fetch_trove import fetch_many
    from app.archive_detective.summarize_async import queue_summary, research_status
    from app.context_store import upsert_item, sid_from
except ImportError as e:
    logging.warning(f"Could not import research modules: {e}")
    fetch_many = None
    queue_summary = None
    research_status = {}
    upsert_item = None
    sid_from = None

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/research")
async def research(
    request: Request,
    deep: bool = Query(False, description="Enable deep research mode (more pages)"),
    pages: int = Query(5, ge=1, le=20, description="Number of pages to fetch (100 articles per page)")
):
    """High-volume research endpoint that fetches hundreds of Trove articles."""
    if not fetch_many or not upsert_item or not sid_from:
        return JSONResponse(
            status_code=503,
            content={"error": "Research modules not available", "detail": "Required modules could not be imported"}
        )
    
    try:
        data = await request.json()
        query = data.get("query", "")
        if not query:
            return JSONResponse(
                status_code=400,
                content={"error": "Query required", "detail": "Please provide a 'query' field in the request body"}
            )
        
        # Override pages from query params if provided
        if "pages" in data:
            pages = int(data.get("pages", pages))
        if deep:
            pages = max(pages, 10)  # Deep mode uses at least 10 pages
        
        api_key = os.getenv("TROVE_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=500,
                content={"error": "TROVE_API_KEY not configured", "detail": "Set TROVE_API_KEY environment variable"}
            )
        
        # Generate job ID for status tracking
        job_id = str(uuid.uuid4())
        research_status[job_id] = {
            "query": query,
            "status": "fetching",
            "total": 0,
            "processed": 0,
            "summarized": 0,
            "pages": pages,
            "deep": deep
        }
        
        # Get session ID
        sid = sid_from(
            dict(request.headers),
            request.client.host if request.client else "127.0.0.1",
            request.headers.get("user-agent", "")
        )
        
        # Fetch articles (synchronous, but we'll make it async-friendly)
        logger.info(f"Starting research for query: {query}, pages: {pages}, deep: {deep}")
        research_status[job_id]["status"] = "fetching"
        
        # Run fetch in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(None, fetch_many, query, api_key, pages, 0.5)
        
        research_status[job_id]["total"] = len(records)
        research_status[job_id]["status"] = "processing"
        
        # Upsert articles and queue summaries
        for r in records:
            try:
                upsert_item(sid, {
                    "trove_id": r["id"],
                    "title": r["title"],
                    "date": r["date"],
                    "source": r["source"],
                    "url": r["url"],
                    "snippet": r["snippet"],
                })
                
                # Queue for summarization
                text = r.get("snippet") or r.get("title", "")
                if text:
                    await queue_summary(sid, r["id"], text, job_id)
                
                research_status[job_id]["processed"] = research_status[job_id].get("processed", 0) + 1
            except Exception as e:
                logger.warning(f"Error processing article {r.get('id')}: {e}")
        
        research_status[job_id]["status"] = "queued"  # Summarization is queued
        
        return JSONResponse(content={
            "ok": True,
            "count": len(records),
            "deep": deep,
            "pages": pages,
            "job_id": job_id,
            "status": "queued",
            "message": f"Fetched {len(records)} articles. Summarization in progress."
        })
        
    except Exception as e:
        logger.error(f"Research endpoint error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Research failed", "detail": str(e)}
        )

@router.get("/api/research/status/{job_id}")
async def get_research_status(job_id: str):
    """Get status of a research job."""
    if job_id not in research_status:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found", "detail": f"Job ID {job_id} not found"}
        )
    
    status = research_status[job_id].copy()
    
    # Calculate progress percentage
    total = status.get("total", 0)
    processed = status.get("processed", 0)
    summarized = status.get("summarized", 0)
    
    if total > 0:
        status["progress_fetch"] = min(100, int((processed / total) * 100))
        status["progress_summarize"] = min(100, int((summarized / total) * 100))
    else:
        status["progress_fetch"] = 0
        status["progress_summarize"] = 0
    
    # Determine overall status
    if status["status"] == "fetching":
        status["overall_progress"] = status["progress_fetch"] // 2
    elif status["status"] == "processing":
        status["overall_progress"] = 50 + (status["progress_fetch"] // 2)
    elif status["status"] == "queued":
        status["overall_progress"] = 50 + (status["progress_summarize"] // 2)
    else:
        status["overall_progress"] = 100
    
    return JSONResponse(content=status)

