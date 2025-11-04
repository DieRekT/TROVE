import os

import orjson
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from .adapters.trove import search_trove
from .deps import get_cache, get_http_client
from .models import NormalizedItem, SearchResponse
from .schemas import ReadyResponse
from .utils.csv_export import items_to_csv_bytes

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


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
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


@app.get("/")
async def root():
    return PlainTextResponse("Archive Detective API. Use /search?q=term")
