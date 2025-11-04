"""FastAPI application main module with modern patterns."""

import logging
import os
from io import BytesIO
from typing import Annotated

import httpx
import qrcode
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from app.archive_detective import init_archive_detective
from app.config import get_settings
from app.dependencies import get_trove_client
from app.exceptions import ConfigurationError, NetworkError, TroveAPIError, TroveAppError
from app.services import TroveSearchService
from app.trove_client import TroveClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Modern Trove search interface using API v3",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount outputs directory for saved images, reports, etc.
from pathlib import Path

outputs_dir = Path("outputs")
outputs_dir.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=str(outputs_dir)), name="files")

# Initialize templates
templates_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

# Initialize Archive Detective if enabled
if os.getenv("ARCHIVE_DETECTIVE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
    init_archive_detective(app)

# Add context API router
from app.context_api import router as context_router
app.include_router(context_router)

# Initialize context store database
try:
    from app.context_store import ensure_db
    ensure_db()
    logger.info("Context store database initialized")
except Exception as e:
    logger.warning(f"Failed to initialize context store: {e}")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Home Dashboard - Troveing main entry point."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    
    # Get timezone
    tz = ZoneInfo("Australia/Sydney")
    now = datetime.now(tz)
    
    # Count today's files (simplified - would use proper database in production)
    outputs_dir = Path("outputs")
    queries_dir = Path("queries")
    docs_dir = Path("docs")
    
    today_runs = 0
    total_queries = len(list(queries_dir.glob("*.csv"))) if queries_dir.exists() else 0
    total_docs = len(list(docs_dir.glob("*.pdf"))) if docs_dir.exists() else 0
    total_outputs = len(list(outputs_dir.glob("*"))) if outputs_dir.exists() else 0
    
    context = {
        "request": request,
        "today_runs": today_runs,
        "total_queries": total_queries,
        "total_docs": total_docs,
        "total_outputs": total_outputs,
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
    
    template = templates_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "api_configured": bool(settings.trove_api_key),
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Annotated[str, Query(description="Search query string")] = "",
    category: Annotated[
        str,
        Query(
            description="Content category",
            pattern="^(newspaper|magazine|book|image|research|diary|music|list|people|all)$",
        ),
    ] = "newspaper",
    n: Annotated[int, Query(ge=1, le=100, description="Number of results")] = 20,
    s: Annotated[int, Query(ge=0, description="Start offset")] = 0,
    show_images: Annotated[bool, Query(description="Show image thumbnails")] = True,
    l_format: Annotated[str | None, Query(description="Format filter")] = None,
    l_artType: Annotated[str | None, Query(description="Art type filter")] = None,
    l_place: Annotated[str | None, Query(description="Place filter")] = None,
    sortby: Annotated[
        str | None,
        Query(description="Sort order"),
    ] = None,
    year_from: Annotated[int | None, Query(ge=1800, le=2024, description="Year from")] = None,
    year_to: Annotated[int | None, Query(ge=1800, le=2024, description="Year to")] = None,
    client: TroveClient = Depends(get_trove_client),
):
    """Main search endpoint."""
    # Normalize empty strings to None and validate sortby
    if sortby == "":
        sortby = None
    elif sortby is not None and sortby not in ["relevance", "dateAsc", "dateDesc"]:
        raise HTTPException(
            status_code=400,
            detail=f"sortby must be one of: relevance, dateAsc, dateDesc (got: {sortby})",
        )

    # Validate query - Trove API may not accept completely empty queries for specific categories
    # Allow whitespace-only queries but warn
    q_clean = q.strip() if q else ""

    # Some categories require a non-empty query - validate before making API call
    categories_requiring_query = [
        "newspaper",
        "magazine",
        "book",
        "image",
        "research",
        "diary",
        "music",
        "list",
        "people",
    ]

    # Normalize filter parameters - remove whitespace, set to None if empty
    l_format_clean = l_format.strip() if l_format and l_format.strip() else None
    l_artType_clean = l_artType.strip() if l_artType and l_artType.strip() else None
    l_place_clean = l_place.strip() if l_place and l_place.strip() else None

    # Handle date range - add to query if specified
    # Trove API supports date range in query: date:[1800 TO 1900]
    q_with_date = q_clean
    if year_from or year_to:
        year_from_val = year_from if year_from else 1800
        year_to_val = year_to if year_to else 2024
        date_range = f"date:[{year_from_val} TO {year_to_val}]"
        if q_clean:
            q_with_date = f"{q_clean} {date_range}"
        else:
            q_with_date = date_range

    # Calculate pagination
    can_paginate = category != "all"
    prev_s = max(0, s - n) if can_paginate else 0
    next_s = s + n if can_paginate else 0

    error_message = None
    items = []
    total = 0

    # Check if query is required but empty - show helpful error without making API call
    if not q_clean and category in categories_requiring_query:
        error_message = (
            f"❌ Query required for '{category}' category.\n\n"
            f"Please enter a search term (e.g., 'australia', 'sydney', 'history').\n"
            f"The '{category}' category requires a search query to work."
        )
        logger.info(f"Skipping API call - empty query for category '{category}'")
    else:
        # Only make API call if we don't have a validation error
        try:
            service = TroveSearchService(client)
            # Use cleaned query - Trove API may reject empty/whitespace-only queries
            items, total = await service.search(
                q=q_with_date,
                category=category,
                n=n,
                s=s,
                l_format=l_format_clean,
                l_artType=l_artType_clean,
                l_place=l_place_clean,
                sortby=sortby,
            )
            logger.info(f"Search successful: {len(items)} items found for query '{q}'")
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            error_message = f"Configuration error: {str(e)}"
        except TroveAPIError as e:
            logger.error(
                f"Trove API error {e.status_code}: {e.response_text}\n"
                f"Request params: q={q}, category={category}, n={n}, s={s}, "
                f"l_format={l_format}, l_artType={l_artType}, l_place={l_place}, sortby={sortby}"
            )
            # Show full error response
            if e.response_text:
                try:
                    import json

                    error_json = (
                        json.loads(e.response_text) if e.response_text.startswith("{") else None
                    )
                    if error_json:
                        error_message = (
                            f"Trove API error {e.status_code}: "
                            f"{error_json.get('statusText', 'Error')} - "
                            f"{error_json.get('description', e.response_text[:300])}"
                        )
                    else:
                        error_message = f"Trove API error {e.status_code}: {e.response_text[:500]}"
                except (json.JSONDecodeError, ValueError, TypeError):
                    # JSON parsing failed, use raw response text
                    error_message = f"Trove API error {e.status_code}: {e.response_text[:500]}"
            else:
                error_message = f"Trove API error {e.status_code}: An unexpected error occurred"

            # Add helpful suggestions
            if e.status_code == 500:
                error_message += (
                    "\n\nPossible causes: "
                    "• API service issue (try again later) "
                    "• Invalid parameter combination "
                    "• Rate limiting (wait a moment) "
                    "• Check your API key is valid"
                )
        except NetworkError as e:
            logger.error(f"Network error: {e}")
            error_message = f"Network error: {str(e)}"
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            error_message = f"Data validation error: {str(e)}"
        except TroveAppError as e:
            logger.error(f"Application error: {e}")
            error_message = f"Error: {str(e)}"
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            error_message = f"Unexpected error: {type(e).__name__}: {str(e)}"

    try:
        context = {
            "request": request,
            "q": q_clean,
            "category": category,
            "items": [item.model_dump(mode="json") for item in items],
            "n": n,
            "s": s,
            "prev_s": prev_s,
            "next_s": next_s,
            "show_images": show_images,
            "l_format": l_format_clean or "",
            "l_artType": l_artType_clean or "",
            "l_place": l_place_clean or "",
            "sortby": sortby or "",
            "year_from": year_from,
            "year_to": year_to,
            "total": total,
            "api_key_present": bool(settings.trove_api_key),
            "error": error_message,
            "can_paginate": can_paginate,
        }

        template = templates_env.get_template("search.html")
        
        # Prepare items for template - map field names to template expectations
        items_dict = []
        for item in items:
            item_data = item.model_dump(mode="json")
            # Map model fields to template field names
            items_dict.append({
                "id": item_data.get("id"),
                "title": item_data.get("title"),
                "date": item_data.get("issued"),
                "source": item_data.get("publisher_or_source"),
                "url": item_data.get("trove_url"),
                "snippet": item_data.get("snippet"),
                "thumbnail": item_data.get("image_thumb"),
                "image_full": item_data.get("image_full"),
                "category": item_data.get("category"),
            })
        
        # Build query string for pagination
        query_params = []
        if q_clean:
            query_params.append(f"q={q_clean}")
        if category:
            query_params.append(f"category={category}")
        if year_from:
            query_params.append(f"year_from={year_from}")
        if year_to:
            query_params.append(f"year_to={year_to}")
        if l_place_clean:
            query_params.append(f"l_place={l_place_clean}")
        if l_format_clean:
            query_params.append(f"l_format={l_format_clean}")
        if sortby:
            query_params.append(f"sortby={sortby}")
        query_params.append(f"n={n}")
        query_string = "&".join(query_params)
        
        # Update context with mapped items and query string
        context["items"] = items_dict
        context["query_string"] = query_string
        
        # Add search results to research context (limit to first 10 to avoid overwhelming)
        try:
            from app.archive_detective.research_context import add_article_to_context
            session_key = _get_session_key(request)
            for item in items_dict[:10]:  # Only track first 10 results
                add_article_to_context(session_key, item)
        except Exception as ctx_err:
            logger.warning(f"Failed to add search results to context: {ctx_err}")
        
        html = template.render(**context)
        # Always return 200 - show empty state if no query
        status_code = 200
        return HTMLResponse(content=html, status_code=status_code)
    except Exception as e:
        logger.exception(f"Template rendering error: {e}")
        return HTMLResponse(
            content=f"<h1>Internal Server Error</h1><p>{str(e)}</p>", status_code=500
        )


@app.get("/reader", response_class=HTMLResponse)
async def reader(
    request: Request, 
    id: str = Query(...),
    url: str = Query(None),
    snippet: str = Query(None),
    title: str = Query(None),
    date: str = Query(None),
    source: str = Query(None),
):
    """Reader mode with TTS and side-by-side view."""
    from app.archive_detective.article_io import fetch_item_text
    from app.archive_detective.research_context import add_article_to_context
    
    # Fetch article - pass both ID and URL if available
    data = await fetch_item_text(id, url)
    
    # If fetch failed but we have snippet/title from search results, use those
    if not data.get("ok"):
        if snippet or title:
            # Use search result data as fallback
            data = {
                "ok": True,
                "id": id,
                "title": title or "Untitled Article",
                "date": date or "",
                "source": source or "",
                "url": url or "",
                "text": snippet or "Full text not available. This article may only have a snippet available from the search results.",
                "snippet": snippet or "",
            }
        else:
            error = data.get("error", "Failed to fetch article")
            # Return user-friendly error page
            return HTMLResponse(
                content=f"""
                <html>
                <head><title>Reader - Troveing</title>
                <link rel="stylesheet" href="/static/style.css">
                </head>
                <body>
                <div style="padding: 2rem; max-width: 800px; margin: 0 auto;">
                    <h1>Article Not Available</h1>
                    <p>{error}</p>
                    <p>This article may not have full text available, or the ID may be incorrect.</p>
                    <p><a href="/search">← Back to Search</a> | <a href="/dashboard">Dashboard</a></p>
                </div>
                </body>
                </html>
                """,
                status_code=200
            )
    
    # Ensure we have at least some content
    if not data.get("text") and not data.get("snippet"):
        data["text"] = snippet or "No text content available for this article."
    
    # Use provided URL if available and not in data
    if url and not data.get("url"):
        data["url"] = url
    
    # Override with provided metadata if available (from search results)
    if title:
        data["title"] = title
    if date:
        data["date"] = date
    if source:
        data["source"] = source
    if snippet and not data.get("text"):
        data["text"] = snippet
    
    # Add article to research context for AI reference
    try:
        session_key = _get_session_key(request)
        add_article_to_context(session_key, data)
    except Exception as ctx_err:
        logger.warning(f"Failed to add article to context: {ctx_err}")
    
    context = {
        "request": request,
        "article": data,
    }
    
    template = templates_env.get_template("reader.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/api/item/{item_id}")
async def get_item(item_id: str, request: Request, client: TroveClient = Depends(get_trove_client)):
    """Get item details for preview."""
    from app.archive_detective.article_io import fetch_item_text
    from app.archive_detective.research_context import add_article_to_context
    from app.services import TroveSearchService
    
    try:
        # First try: fetch full article text (best for newspapers)
        article_data = await fetch_item_text(item_id)
        if article_data.get("ok"):
            result = {
                "id": article_data.get("id", item_id),
                "title": article_data.get("title", "Untitled"),
                "date": article_data.get("date", ""),
                "source": article_data.get("source", ""),
                "snippet": article_data.get("text", article_data.get("snippet", ""))[:500],
                "url": article_data.get("url", ""),
                "text": article_data.get("text", ""),
            }
            # Add to research context
            try:
                session_key = _get_session_key(request)
                add_article_to_context(session_key, result)
            except Exception as ctx_err:
                logger.warning(f"Failed to add article to context: {ctx_err}")
            return result
        
        # Second try: search for item by constructing Trove URL pattern
        # Trove article IDs are often in format: nla.news-article{ID}
        service = TroveSearchService(client)
        
        # Try searching with the ID directly
        try:
            # Search with ID - Trove sometimes allows direct ID searches
            search_results, _ = await service.search(q=item_id, category="all", n=20, s=0)
            
            # Find matching item by ID
            for item in search_results:
                item_data = item.model_dump(mode="json")
                item_id_from_data = str(item_data.get("id", ""))
                
                        # Match if IDs are equal or if one ends with the other
                if (item_id_from_data == item_id or 
                    item_id_from_data.endswith(item_id) or 
                    item_id.endswith(item_id_from_data)):
                    result = {
                        "id": item_data.get("id", item_id),
                        "title": item_data.get("title", "Untitled"),
                        "date": item_data.get("issued", ""),
                        "source": item_data.get("publisher_or_source", ""),
                        "snippet": item_data.get("snippet", "")[:500] if item_data.get("snippet") else "",
                        "url": item_data.get("trove_url", ""),
                        "thumbnail": item_data.get("image_thumb"),
                    }
                    # Add to research context
                    try:
                        session_key = _get_session_key(request)
                        add_article_to_context(session_key, result)
                    except Exception as ctx_err:
                        logger.warning(f"Failed to add article to context: {ctx_err}")
                    return result
        except Exception as search_err:
            logger.warning(f"Search fallback failed for {item_id}: {search_err}")
        
        # Last resort: return minimal info with helpful message
        result = {
            "id": item_id,
            "title": "Item details unavailable",
            "date": "",
            "source": "",
            "snippet": f"Full details for item {item_id} could not be loaded. Try opening it in the Reader for full text.",
            "url": f"https://trove.nla.gov.au/newspaper/article/{item_id}",
        }
    except Exception as e:
        logger.exception(f"Error fetching item {item_id}: {e}")
        result = {
            "id": item_id,
            "title": "Error loading item",
            "date": "",
            "source": "",
            "snippet": f"Error: {str(e)}",
            "url": "",
        }
    
    # Add to research context if we have basic info
    try:
        if result.get("id") and result.get("title") and result.get("title") != "Error loading item":
            session_key = _get_session_key(request)
            add_article_to_context(session_key, result)
    except Exception as ctx_err:
        logger.warning(f"Failed to add article to context: {ctx_err}")
    
    return result


@app.post("/api/collections/add")
async def add_to_collection(body: dict = Body(...)):
    """Add item to collection."""
    item_id = body.get("item_id")
    # This would save to database/collection
    return {"ok": True, "message": "Item added to collection"}


@app.post("/api/explain")
async def explain_text(body: dict = Body(...)):
    """Explain selected text using AI."""
    text = body.get("text", "")
    if not text:
        return {"error": "No text provided"}
    
    try:
        # Try using Archive Detective chat LLM if available
        from app.archive_detective import chat_llm
        if chat_llm.is_enabled():
            prompt = f"Explain this text in simple terms, suitable for historical research: {text}"
            routed = chat_llm.route_message(prompt)
            if routed and "say" in routed:
                return {"explanation": routed["say"]}
        
        # Fallback: basic explanation
        return {"explanation": f"This text appears to be about: {text[:100]}... It may refer to historical events, people, or places from the period."}
    except Exception as e:
        logger.exception(f"Error explaining text: {e}")
        return {"explanation": f"Could not generate explanation: {str(e)}"}


@app.post("/api/define")
async def define_text(body: dict = Body(...)):
    """Define selected text using dictionary/AI."""
    text = body.get("text", "")
    if not text:
        return {"error": "No text provided"}
    
    try:
        # Try using Archive Detective chat LLM if available
        from app.archive_detective import chat_llm
        if chat_llm.is_enabled():
            prompt = f"Provide a brief dictionary-style definition for this term or phrase: {text}"
            routed = chat_llm.route_message(prompt)
            if routed and "say" in routed:
                return {"definition": routed["say"]}
        
        # Fallback: basic definition
        return {"definition": f"'{text}' is a term or phrase that may have historical or cultural significance."}
    except Exception as e:
        logger.exception(f"Error defining text: {e}")
        return {"definition": f"Could not generate definition: {str(e)}"}


@app.post("/api/translate")
async def translate_text(body: dict = Body(...), target_lang: str = Query("en")):
    """Translate selected text using AI."""
    text = body.get("text", "")
    if not text:
        return {"error": "No text provided"}
    
    try:
        # Try using Archive Detective chat LLM if available
        from app.archive_detective import chat_llm
        if chat_llm.is_enabled():
            prompt = f"Translate this text to {target_lang}, preserving historical context: {text}"
            routed = chat_llm.route_message(prompt)
            if routed and "say" in routed:
                return {"translation": routed["say"], "original": text, "target": target_lang}
        
        # Fallback: return original with note
        return {"translation": f"[Translation unavailable] Original: {text}", "original": text, "target": target_lang}
    except Exception as e:
        logger.exception(f"Error translating text: {e}")
        return {"translation": f"Could not translate: {str(e)}", "original": text}


@app.post("/api/notes/add")
async def add_note(body: dict = Body(...)):
    """Add note to collection."""
    # This would save to notes
    return {"ok": True, "message": "Note added"}


@app.get("/api/local-ip")
async def get_local_ip():
    """Get the local network IP address for mobile device connection."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return {"ip": ip, "ok": True}
    except Exception:
        return {"ip": None, "ok": False}


@app.get("/desk", response_class=HTMLResponse)
async def desk(request: Request):
    """Research Desk - AI conversation interface."""
    context = {"request": request}
    template = templates_env.get_template("desk.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/collections", response_class=HTMLResponse)
async def collections(request: Request):
    """Collections - Board view."""
    context = {"request": request}
    template = templates_env.get_template("collections.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/studio", response_class=HTMLResponse)
async def studio(request: Request):
    """Report Studio - Drafting interface."""
    context = {"request": request}
    template = templates_env.get_template("studio.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/timeline", response_class=HTMLResponse)
async def timeline_page(request: Request):
    """Timeline - Event ribbon view."""
    context = {"request": request}
    template = templates_env.get_template("timeline.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Status page - System monitoring."""
    from pathlib import Path
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    tz = ZoneInfo("Australia/Sydney")
    now = datetime.now(tz)
    
    outputs_dir = Path("outputs")
    queries_dir = Path("queries")
    docs_dir = Path("docs")
    
    total_queries = len(list(queries_dir.glob("*.csv"))) if queries_dir.exists() else 0
    total_docs = len(list(docs_dir.glob("*.pdf"))) if docs_dir.exists() else 0
    total_outputs = len(list(outputs_dir.glob("*"))) if outputs_dir.exists() else 0
    
    # Check tunnel status
    tunnel_status = {"ok": False, "url": None}
    try:
        from pyngrok import ngrok
        tunnels = ngrok.get_tunnels()
        if tunnels:
            tunnel_status = {"ok": True, "url": tunnels[0].public_url}
    except:
        pass
    
    context = {
        "request": request,
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "total_queries": total_queries,
        "total_docs": total_docs,
        "total_outputs": total_outputs,
        "tunnel_status": tunnel_status,
        "api_key_configured": bool(settings.trove_api_key),
    }
    
    template = templates_env.get_template("status.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/api/timeline")
async def api_timeline():
    """API endpoint for timeline data."""
    return {"ok": True, "events": []}


@app.get("/api/tunnel/status")
async def get_tunnel_status():
    """Check if ngrok tunnel is active for this server."""
    try:
        from pyngrok import ngrok
        tunnels = ngrok.get_tunnels()
        if tunnels:
            tunnel_url = tunnels[0].public_url
            return {"ok": True, "url": tunnel_url}
    except Exception:
        pass
    # Also try checking via ngrok API if pyngrok fails
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                http_tunnels = [t for t in tunnels if t.get("proto") == "http"]
                if http_tunnels:
                    tunnel_url = http_tunnels[0].get("public_url")
                    return {"ok": True, "url": tunnel_url}
    except Exception:
        pass
    return {"ok": False, "url": None, "message": "No tunnel active. Run 'ngrok http 8000' or use /api/tunnel/start"}


@app.post("/api/tunnel/start")
async def start_tunnel():
    """Start ngrok tunnel for this server."""
    try:
        from pyngrok import ngrok
        port = int(os.getenv("PORT", "8000"))
        tunnel = ngrok.connect(port, "http")
        return {"ok": True, "url": tunnel.public_url, "message": "Tunnel started"}
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "Run 'ngrok http 8000' manually"}


@app.get("/api/tunnel/public-url")
async def get_public_tunnel_url():
    """Get public tunnel URL - accessible without localhost. Returns the public ngrok URL."""
    try:
        from pyngrok import ngrok
        tunnels = ngrok.get_tunnels()
        if tunnels:
            return {"ok": True, "url": tunnels[0].public_url, "message": "Tunnel active"}
    except Exception:
        pass
    # Fallback: check ngrok API
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                http_tunnels = [t for t in tunnels if t.get("proto") == "http"]
                if http_tunnels:
                    return {"ok": True, "url": http_tunnels[0].get("public_url"), "message": "Tunnel active"}
    except Exception:
        pass
    return {"ok": False, "url": None, "message": "No tunnel active. Visit the web app and click '📱 Connect' to start one."}


@app.get("/api/files/list")
async def list_files():
    """List all files available in the /files directory."""
    try:
        from datetime import datetime
        
        files_list = []
        outputs_dir = Path("outputs")
        
        if outputs_dir.exists():
            # List all files (not directories) recursively
            for file_path in outputs_dir.rglob("*"):
                if file_path.is_file():
                    # Get relative path from outputs_dir
                    rel_path = file_path.relative_to(outputs_dir)
                    file_size = file_path.stat().st_size
                    modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    files_list.append({
                        "name": str(rel_path),
                        "path": f"/files/{rel_path}",
                        "size": file_size,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                        "modified": modified_time.isoformat(),
                    })
        
        # Sort by modified time (newest first)
        files_list.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "ok": True,
            "files": files_list,
            "count": len(files_list),
        }
    except Exception as e:
        logger.exception(f"Error listing files: {e}")
        return {
            "ok": False,
            "error": str(e),
            "files": [],
            "count": 0,
        }


@app.get("/api/qrcode")
async def get_qrcode(request: Request, url: str = Query(None)):
    """Generate QR code for web app URL (not API - points to the actual web app)."""
    if not url:
        # Get the current web app URL (not API)
        base_url = f"{request.url.scheme}://{request.url.hostname}"
        if request.url.port:
            base_url += f":{request.url.port}"
        
        # Check for tunnel on web app port (8000) or mobile API port (8001)
        # Try to get tunnel URL from mobile API server first
        mobile_api_base = os.getenv("MOBILE_API_BASE", "http://127.0.0.1:8001")
        tunnel_url = None
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                tunnel_response = await client.get(f"{mobile_api_base}/api/tunnel/status")
                if tunnel_response.status_code == 200:
                    tunnel_data = tunnel_response.json()
                    if tunnel_data.get("ok") and tunnel_data.get("url"):
                        # Extract base URL from tunnel (remove /api if present)
                        tunnel_url = tunnel_data["url"].replace("/api", "")
        except Exception:
            pass
        
        # If we have a tunnel, use it (but point to web app, not API)
        if tunnel_url:
            url = tunnel_url
        else:
            # No tunnel, use local network IP
            import socket
            hostname = request.url.hostname
            
            # If localhost, try to get actual LAN IP
            if hostname in ("127.0.0.1", "localhost"):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    hostname = s.getsockname()[0]
                    s.close()
                except Exception:
                    pass
            
            # Use web app port (8000), not API port
            web_port = request.url.port or 8000
            url = f"http://{hostname}:{web_port}"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    
    return Response(content=img_bytes.read(), media_type="image/png")
