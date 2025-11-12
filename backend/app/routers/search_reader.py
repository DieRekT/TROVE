from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.templating import Jinja2Templates
from ..adapters.trove import search_trove
from ..deps import get_http_client, get_cache
from fastapi import Depends
import httpx

router = APIRouter(tags=["search", "reader"])
template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Add static_url function to templates
def static_url(request, path: str) -> str:
    """Generate URL for static files."""
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/{path.lstrip('/')}"

templates.env.globals["static_url"] = static_url


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = Query("", min_length=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    """Search page with results."""
    items = []
    total = 0
    if q:
        try:
            data = await search_trove(client, q=q, page=page, page_size=page_size)
            items = data.get("items", [])
            total = int(data.get("total", 0))
        except Exception as e:
            # Graceful error handling
            pass
    
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/reader", response_class=HTMLResponse)
async def reader_page(
    request: Request,
    id: str = Query(..., description="Article ID or Trove URL"),
):
    """Reader page for viewing articles."""
    # Try to fetch article details
    article = {
        "id": id,
        "title": "Loading...",
        "text": "",
        "url": f"https://trove.nla.gov.au/newspaper/article/{id}" if id.isdigit() else id,
        "date": None,
        "source": None,
    }
    
    # Attempt to fetch article text (simplified - can be enhanced)
    try:
        # This would need a proper article fetcher - for now, return basic template
        pass
    except Exception:
        pass
    
    return templates.TemplateResponse(
        "reader.html",
        {
            "request": request,
            "article": article,
        }
    )


@router.get("/research", response_class=HTMLResponse)
async def research_page(
    request: Request,
    seed: str = Query("", description="Seed query for research"),
):
    """Deep research page."""
    return templates.TemplateResponse(
        "research.html",
        {
            "request": request,
            "seed_query": seed,
        }
    )

