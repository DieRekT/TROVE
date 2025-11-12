import os
from pathlib import Path

import orjson
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .adapters.trove import search_trove
from .deps import get_cache, get_http_client
from .models import NormalizedItem, SearchResponse
from .schemas import ReadyResponse
from .utils.csv_export import items_to_csv_bytes
from .routers import deep_research, formatting, dashboard, batch_research, search_reader, reader_text, summarize, tunnel, qrcode, context, pages, items, text_tools, mobile_api, structured_synthesis, research, entities, timeline, analysis, seeds

app = FastAPI(title="Archive Detective API", version="0.1.0")

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ready", response_model=ReadyResponse)
async def ready(cache=Depends(get_cache)):
    return ReadyResponse(ok=True, cache=cache.backend_name())


@app.get("/api/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    """JSON API endpoint for search (moved to /api/search to avoid conflict with HTML page)."""
    cache_key = f"trove:{q}:{page}:{page_size}"
    cached = await cache.get(cache_key)
    if cached:
        data = orjson.loads(cached)
        return SearchResponse(q=q, page=page, page_size=page_size, total=data["total"], items=data["items"])  # type: ignore

    try:
        data = await search_trove(client, q=q, page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # persist compact cache
    await cache.set(cache_key, orjson.dumps(data).decode("utf-8"))

    items = [NormalizedItem(**it) for it in data["items"]]
    return SearchResponse(
        q=q, page=page, page_size=page_size, total=int(data["total"]), items=items
    )


@app.get("/export")
async def export(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    format: str = Query("csv", pattern="^(csv|json)$"),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    # NOTE: export always fetches fresh for requested page/page_size; Phase‑2 will add multi‑page export
    data = await search_trove(client, q=q, page=page, page_size=page_size)
    items = data.get("items", [])

    if format == "json":
        payload = orjson.dumps(items)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=export-{q}.json"},
        )

    # csv
    csv_bytes = items_to_csv_bytes(items)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=export-{q}.csv"},
    )


app.include_router(search_reader.router)  # Include search_reader router FIRST so /search HTML page takes precedence
app.include_router(deep_research.router)
app.include_router(formatting.router)
app.include_router(dashboard.router)
app.include_router(batch_research.router)
app.include_router(reader_text.router)
app.include_router(summarize.router)
app.include_router(tunnel.router)
app.include_router(qrcode.router)
app.include_router(context.router)
app.include_router(pages.router)
app.include_router(items.router)
app.include_router(text_tools.router)
app.include_router(mobile_api.router)
app.include_router(structured_synthesis.router)
app.include_router(research.router)
app.include_router(entities.router)
app.include_router(timeline.router)
app.include_router(analysis.router)
app.include_router(seeds.router)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.post("/api/tts/stream")
async def tts_stream():
    """TTS endpoint stub - returns 501 Not Implemented if TTS server absent."""
    return JSONResponse(
        status_code=501,
        content={"error": "TTS service not implemented", "detail": "Text-to-speech is not available. Use browser SpeechSynthesis API as fallback."}
    )


@app.get("/api/tts/health")
async def tts_health():
    """Check TTS service availability."""
    # TTS is not implemented, return unavailable
    return JSONResponse(
        status_code=503,
        content={"available": False, "message": "TTS service not implemented. Use browser SpeechSynthesis API."}
    )


@app.get("/")
async def root():
    """Redirect root to dashboard."""
    return RedirectResponse(url="/dashboard", status_code=302)


@app.on_event("startup")
async def start_background_tasks():
    """Start background workers on application startup."""
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Start summary worker if available
    try:
        import sys
        from pathlib import Path
        root_path = Path(__file__).parent.parent.parent.parent
        if str(root_path) not in sys.path:
            sys.path.insert(0, str(root_path))
        
        from app.archive_detective.summarize_async import summary_worker
        asyncio.create_task(summary_worker())
        logger.info("✅ Background summary worker started")
    except ImportError as e:
        logger.warning(f"Could not start summary worker: {e}")
    except Exception as e:
        logger.error(f"Error starting background tasks: {e}")
