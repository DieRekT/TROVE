"""FastAPI application main module with modern patterns."""

import asyncio
from collections import Counter, defaultdict
import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from io import BytesIO
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx
import qrcode
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from app.archive_detective import fetch_item_text, init_archive_detective, normalize_trove_id
from app.context_store import (
    delete_kingfisher_cards,
    get_article as get_context_article,
    list_kingfisher_cards,
    list_article_images,
    save_kingfisher_cards,
    sid_from,
    upsert_item as upsert_context_item,
    update_article_full_text,
    update_article_summary,
)
from app.config import get_settings
from app.dependencies import get_trove_client
from app.exceptions import ConfigurationError, NetworkError, TroveAPIError, TroveAppError
from app.services import refresh_article_images, TroveSearchService
from app.summarizer import stream_card_summary, summarize_cards as summarize_cards_structured
from app.trove_client import TroveClient
from app.types import (
    BriefImage,
    BriefResponse,
    BriefSection,
    Card,
    CardList,
    CardSummary,
    PinMetadata,
)
from backend.kingfisher.summarizer import summarize_cards as summarize_cards_text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title="Troveing - Research Partner",
    version=settings.app_version,
    description="Modern Trove search interface using API v3",
    docs_url="/docs",  # Enable docs at /docs (accessible at /trove/docs when mounted)
    redoc_url="/redoc",  # Enable redoc at /redoc
    openapi_url="/openapi.json",  # OpenAPI JSON at /openapi.json
)

# Add middleware to strip empty query params (fixes year_to="" validation error)
from app.middleware.strip_empty import StripEmptyQueryParamsMiddleware
app.add_middleware(StripEmptyQueryParamsMiddleware, keys=["year_from", "year_to"])

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

# Add global template function to get static file URLs
# This will be set per-request in the template context
def get_static_url(request: Request, path: str) -> str:
    """Return a fully-qualified URL for static assets."""
    path = path.lstrip("/")
    if path.startswith("static/"):
        path = path[len("static/") :]
    try:
        url = str(request.url_for("static", path=path))
    except Exception:  # pragma: no cover - fallback when url_for unavailable
        base_url = str(request.base_url).rstrip("/")
        url = f"{base_url}/static/{path}"

    version = getattr(settings, "app_version", None)
    if version:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}v={version}"
    return url

templates_env.globals["static_url"] = get_static_url

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: str | None) -> str:
    """Convert potentially HTML-rich text to readable plain text."""
    if not value:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = _HTML_TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _session_id_from_request(request: Request) -> str:
    """Derive the context store session identifier from the incoming request."""
    client_host = request.client.host if request.client else "127.0.0.1"
    return sid_from(dict(request.headers), client_host, request.headers.get("user-agent", ""))


_SUMMARY_CACHE_TTL = int(os.getenv("KINGFISHER_SUMMARY_TTL_SECONDS", "43200"))
_SUMMARY_CACHE: dict[str, dict[str, Any]] = {}


def _cards_signature(cards: list[Card]) -> str:
    payload = [
        {
            "type": card.type,
            "title": card.title,
            "content": card.content,
            "metadata": card.metadata,
        }
        for card in cards
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _get_cached_summary(article_id: str, signature: str) -> dict[str, Any] | None:
    entry = _SUMMARY_CACHE.get(article_id)
    if not entry:
        return None
    if entry.get("signature") != signature:
        return None
    generated_at = entry.get("generated_at")
    if not generated_at or (time.time() - float(generated_at)) > _SUMMARY_CACHE_TTL:
        return None
    return entry


def _set_cached_summary(
    article_id: str,
    signature: str,
    *,
    summary_text: str,
    summary_struct: dict[str, Any] | None,
    generated_at: float,
) -> None:
    _SUMMARY_CACHE[article_id] = {
        "signature": signature,
        "summary_text": summary_text,
        "summary_struct": summary_struct,
        "generated_at": generated_at,
    }


async def _build_card_summary(
    request: Request,
    metadata: PinMetadata,
    cards: List[Card],
    *,
    refresh_summary: bool = False,
    cards_payload: Optional[List[dict[str, Any]]] = None,
    metadata_payload: Optional[dict[str, Any]] = None,
    signature: Optional[str] = None,
) -> CardSummary:
    """Generate (or retrieve) the structured summary for a set of cards."""
    cards_payload = cards_payload or [
        card.model_dump(mode="json", exclude_none=True) for card in cards
    ]
    metadata_payload = metadata_payload or metadata.model_dump(exclude={"cards"})
    metadata_payload.pop("cards", None)
    signature = signature or _cards_signature(cards)

    cached_entry = None if refresh_summary else _get_cached_summary(metadata.article_id, signature)
    summary_struct: Optional[dict[str, Any]] = None
    summary_text: str
    generated_at: float
    cached = False

    if cached_entry:
        summary_text = str(cached_entry.get("summary_text") or "").strip()
        summary_struct = cached_entry.get("summary_struct")
        generated_at = float(cached_entry.get("generated_at") or time.time())
        cached = True
    else:
        summary_text_future = asyncio.to_thread(summarize_cards_text, cards)
        summary_struct_future = asyncio.to_thread(
            summarize_cards_structured,
            cards_payload,
            metadata_payload,
        )
        summary_text_raw, summary_struct_raw = await asyncio.gather(
            summary_text_future,
            summary_struct_future,
        )
        summary_text = str(summary_text_raw or "").strip() or "Summary unavailable."
        summary_struct = summary_struct_raw if isinstance(summary_struct_raw, dict) else None
        generated_at = time.time()
        _set_cached_summary(
            metadata.article_id,
            signature,
            summary_text=summary_text,
            summary_struct=summary_struct,
            generated_at=generated_at,
        )
        try:
            highlights: Optional[List[str]] = None
            if summary_struct:
                raw_highlights = summary_struct.get("highlights") or []
                if isinstance(raw_highlights, list):
                    highlights = [str(item).strip() for item in raw_highlights if item]
            update_article_summary(
                _session_id_from_request(request),
                metadata.article_id,
                summary_text,
                bullets=highlights,
            )
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.debug("Unable to persist summary for %s: %s", metadata.article_id, exc)

    return CardSummary(
        article_id=metadata.article_id,
        card_count=len(cards),
        summary=summary_struct or summary_text,
        summary_text=summary_text,
        cached=cached,
        generated_at=generated_at,
    )


async def _load_pin_payload(
    request: Request,
    trove_id: str,
    *,
    refresh: bool = False,
) -> tuple[PinMetadata, list[Card], bool]:
    """
    Ensure article metadata and Kingfisher cards exist for the requested pin.

    Returns:
        (metadata, cards, generated_flag)
    """
    normalized_id = normalize_trove_id(trove_id)
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Invalid Trove identifier")

    sid = _session_id_from_request(request)
    article = get_context_article(sid, normalized_id) or {}

    stored_text = article.get("full_text") or article.get("text") or ""
    stored_text = _clean_text(stored_text)
    snippet = article.get("snippet") or ""

    # Optionally refresh existing stored cards
    if refresh and normalized_id:
        delete_kingfisher_cards(normalized_id)

    fetch_payload = None
    if refresh or not article or not stored_text:
        try:
            fetch_payload = await fetch_item_text(normalized_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to fetch article text for %s: %s", normalized_id, exc)
            fetch_payload = {"ok": False}

        if fetch_payload.get("ok"):
            clean_text = _clean_text(fetch_payload.get("text"))
            upsert_context_item(
                sid,
                {
                    "trove_id": normalized_id,
                    "id": normalized_id,
                    "title": fetch_payload.get("title", ""),
                    "date": fetch_payload.get("date", ""),
                    "source": fetch_payload.get("source", ""),
                    "url": fetch_payload.get("url", ""),
                    "snippet": fetch_payload.get("snippet", ""),
                    "text": clean_text,
                },
            )
            if clean_text:
                try:
                    update_article_full_text(sid, normalized_id, clean_text)
                except Exception as exc:  # pragma: no cover
                    logger.debug("Unable to persist full text for %s: %s", normalized_id, exc)
            article = get_context_article(sid, normalized_id) or {}
            stored_text = clean_text or stored_text
            snippet = article.get("snippet") or fetch_payload.get("snippet") or snippet
        elif not article:
            raise HTTPException(status_code=404, detail="Article could not be retrieved")

    summary = article.get("summary")
    summary_bullets = article.get("summary_bullets")

    metadata = PinMetadata(
        article_id=normalized_id,
        title=article.get("title") or article.get("heading") or None,
        date=article.get("date") or article.get("issued") or None,
        source=article.get("source") or article.get("publisher_or_source") or None,
        url=article.get("url") or (fetch_payload.get("url") if fetch_payload else None) or f"https://nla.gov.au/{normalized_id}",
        snippet=snippet or None,
        full_text_available=bool(stored_text),
        summary=summary or None,
        summary_bullets=summary_bullets,
    )

    stored_cards_raw = [] if refresh else list_kingfisher_cards(normalized_id)
    cards: list[Card] = []
    generated = False

    if stored_cards_raw:
        cards = [Card.model_validate(card) for card in stored_cards_raw]
    else:
        text_for_cards = stored_text or snippet
        if text_for_cards:
            metadata_for_cards = {
                "title": metadata.title,
                "date": metadata.date,
                "source": metadata.source,
            }
            try:
                extracted = extract_cards_from_text(text_for_cards, metadata=metadata_for_cards)
            except Exception as exc:  # pragma: no cover
                logger.warning("Kingfisher extraction failed for %s: %s", normalized_id, exc)
                extracted = []

            if extracted:
                generated = True
                payload_to_store = []
                for item in extracted:
                    if isinstance(item, KingfisherCard):
                        payload_to_store.append(item.model_dump())
                    elif isinstance(item, dict):
                        payload_to_store.append(item)
                if payload_to_store:
                    stored_cards = save_kingfisher_cards(normalized_id, payload_to_store)
                    cards = [Card.model_validate(card) for card in stored_cards]
                else:
                    cards = [Card.model_validate(item.model_dump()) for item in extracted if isinstance(item, KingfisherCard)]

    metadata.generated_cards = generated
    return metadata, cards, generated

# Initialize Archive Detective if enabled
if os.getenv("ARCHIVE_DETECTIVE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
    init_archive_detective(app)

# Add context API router
from app.routers import pages
from app.context_api import router as context_router
app.include_router(context_router)
app.include_router(pages.router)
from app.routers import context_alias
app.include_router(context_alias.router)
# Mock search router removed - all endpoints now use real Trove API
# from app.routers import mock_search
# app.include_router(mock_search.router)
from app.routers import agent
app.include_router(agent.router)

# Add fulltext and export routers
from app.routers import articles_fulltext, export as export_router, tts as tts_router
from backend.kingfisher.card_extractor import extract_cards_from_text
from backend.kingfisher.router import router as kingfisher_router
from backend.kingfisher.types import Card as KingfisherCard
app.include_router(articles_fulltext.router)
app.include_router(export_router.router)
app.include_router(tts_router.router)
app.include_router(kingfisher_router)


# Validate API keys at startup
logger.info("Validating API configuration...")
if not settings.trove_api_key:
    logger.error("❌ TROVE_API_KEY is not configured! Search and API features will not work.")
    logger.error("   Set TROVE_API_KEY in .env file")
else:
    logger.info("✅ Trove API key configured")

# Check OpenAI API key for AI features
try:
    from app.archive_detective.config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY is not configured. AI features (Archive Detective, chat) will be disabled.")
        logger.warning("   Set OPENAI_API_KEY in .env file to enable AI features")
    else:
        logger.info("✅ OpenAI API key configured - AI features enabled")
except Exception as e:
    logger.warning(f"Could not check OpenAI API key: {e}")

# Initialize context store database
try:
    from app.context_store import ensure_db
    ensure_db()
    logger.info("Context store database initialized")
except Exception as e:
    logger.warning(f"Failed to initialize context store: {e}")

# Initialize research agent database
try:
    from app.db import Base, engine
    from app import research_models
    Base.metadata.create_all(bind=engine)
    logger.info("Research agent database initialized")
except Exception as e:
    logger.warning(f"Failed to initialize research agent database: {e}")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Home Dashboard - Troveing main entry point."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from app.context_store import sid_from, get_session_stats, list_articles
    
    # Get timezone
    tz = ZoneInfo("Australia/Sydney")
    now = datetime.now(tz)
    
    # Get session ID and stats
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    stats = get_session_stats(sid)
    recent_articles = list_articles(sid, limit=5)
    
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
        "session_stats": stats,
        "recent_articles": recent_articles,
    }
    
    template = templates_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render(**context))


@app.head("/dashboard")
async def dashboard_head():
    """Allow HEAD checks for monitoring/crawler tools."""
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "trove",
        "version": settings.app_version,
        "api_configured": bool(settings.trove_api_key),
    }


@app.get("/healthz")
async def healthz():
    """Health check endpoint for Kubernetes/liveness probes - returns 200 JSON."""
    return {
        "status": "ok",
        "service": "trove",
        "version": settings.app_version,
    }


@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for testing/AI agents.
    Returns detailed status about app readiness including database and dependencies.
    """
    ready = True
    checks = {}
    
    # Check database initialization
    try:
        from app.context_store import ensure_db
        ensure_db()
        checks["context_db"] = "ready"
    except Exception as e:
        checks["context_db"] = f"error: {str(e)}"
        ready = False
    
    try:
        from app.db import Base, engine
        from app import research_models
        # Just check if we can access the engine
        with engine.connect() as conn:
            pass
        checks["research_db"] = "ready"
    except Exception as e:
        checks["research_db"] = f"error: {str(e)}"
        ready = False
    
    # Check API configuration
    checks["trove_api"] = "configured" if settings.trove_api_key else "not_configured"
    
    # Check templates
    try:
        templates_env.get_template("base.html")
        checks["templates"] = "ready"
    except Exception as e:
        checks["templates"] = f"error: {str(e)}"
        ready = False
    
    status_code = 200 if ready else 503
    return Response(
        content=json.dumps({
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "version": settings.app_version,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }),
        media_type="application/json",
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - direct users to the search experience."""
    from fastapi.responses import RedirectResponse
    # Always redirect to search so public tunnel lands on the key entry point
    return RedirectResponse(url="/search", status_code=302)


@app.get("/trove", response_class=HTMLResponse)
async def trove_root(request: Request):
    """Handle /trove path - redirect to search."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/search", status_code=302)


@app.get("/trove/", response_class=HTMLResponse)
async def trove_root_slash(request: Request):
    """Handle /trove/ path - redirect to search."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/search", status_code=302)


@app.get("/pin/{trove_id}", response_model=PinMetadata)
async def get_pin_metadata(
    request: Request,
    trove_id: str,
    refresh: bool = Query(False, description="Force regeneration of stored cards"),
) -> PinMetadata:
    """Return metadata (and cards) for a pinned Trove article."""
    metadata, cards, generated = await _load_pin_payload(request, trove_id, refresh=refresh)
    metadata.cards = cards
    metadata.generated_cards = generated
    return metadata


@app.get("/cards/{trove_id}", response_model=CardList)
async def get_cards_for_article(
    request: Request,
    trove_id: str,
    refresh: bool = Query(False, description="Force regeneration of stored cards"),
) -> CardList:
    """Return the card list for the requested article."""
    metadata, cards, generated = await _load_pin_payload(request, trove_id, refresh=refresh)
    metadata_copy = metadata.model_copy(update={"cards": []})
    return CardList(
        article_id=metadata.article_id,
        cards=cards,
        generated=generated,
        metadata=metadata_copy,
    )


@app.post("/summarize-pin/{trove_id}")
async def summarize_pin(
    request: Request,
    trove_id: str,
    refresh: bool = Query(False, description="Refresh stored cards before summarising"),
    stream: bool = Query(False, description="Stream markdown summary output"),
    response_format: str = Query(
        "json",
        pattern="^(json|text)$",
        description="Set to 'text' to receive a plain-text response.",
    ),
):
    """Summarise cached Kingfisher cards for a Trove article."""
    metadata, cards, _ = await _load_pin_payload(request, trove_id, refresh=refresh)                                                                            
    if not cards:
        raise HTTPException(status_code=404, detail="No knowledge cards available for this article.")

    cards_payload = [card.model_dump(mode="json", exclude_none=True) for card in cards]
    metadata_payload = metadata.model_dump(exclude={"cards"})
    metadata_payload.pop("cards", None)
    signature = _cards_signature(cards)

    if stream:
        async def stream_response():
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def produce() -> None:
                try:
                    for chunk in stream_card_summary(cards_payload, metadata_payload):
                        asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                except Exception as exc:  # pragma: no cover
                    logger.exception("Streaming summary failed for %s: %s", trove_id, exc)
                    asyncio.run_coroutine_threadsafe(queue.put(f"\n[Summary error: {exc}]\n"), loop)
                finally:
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)

            threading.Thread(target=produce, daemon=True).start()

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item

        return StreamingResponse(stream_response(), media_type="text/plain")

    summary_payload = await _build_card_summary(
        request,
        metadata,
        cards,
        refresh_summary=refresh,
        cards_payload=cards_payload,
        metadata_payload=metadata_payload,
        signature=signature,
    )

    if response_format == "text":
        return PlainTextResponse(summary_payload.summary_text or "")

    return {
        "ok": True,
        "article_id": metadata.article_id,
        "card_count": summary_payload.card_count,
        "summary": summary_payload.summary,
        "summary_text": summary_payload.summary_text,
        "cached": summary_payload.cached,
        "generated_at": summary_payload.generated_at,
    }


def _render_brief_markdown(
    metadata: PinMetadata,
    summary: CardSummary,
    sections: List[BriefSection],
    images: List[BriefImage],
) -> str:
    """Render a markdown representation of the compiled brief."""
    lines: List[str] = []

    title = metadata.title or f"Brief for {metadata.article_id}"
    lines.append(f"# {title}")
    lines.append("")

    meta_bits: List[str] = []
    if metadata.date:
        meta_bits.append(f"**Date:** {metadata.date}")
    if metadata.source:
        meta_bits.append(f"**Publication:** {metadata.source}")
    page = getattr(metadata, "page", None)
    if page:
        meta_bits.append(f"**Page:** {page}")
    if meta_bits:
        lines.extend(meta_bits)
        lines.append("")

    summary_body = summary.summary
    if isinstance(summary_body, dict):
        overview = summary_body.get("overview") or summary.summary_text
        if overview:
            lines.append("## Overview")
            lines.append("")
            lines.append(overview.strip())
            lines.append("")
        highlights = summary_body.get("highlights") or []
        if highlights:
            lines.append("## Highlights")
            for item in highlights:
                lines.append(f"- {str(item).strip()}")
            lines.append("")
        notable_quotes = summary_body.get("notable_quotes") or []
        if notable_quotes:
            lines.append("## Notable Quotes")
            for quote in notable_quotes:
                lines.append(f"> {str(quote).strip()}")
            lines.append("")
        next_steps = summary_body.get("next_steps") or []
        if next_steps:
            lines.append("## Suggested Next Steps")
            for step in next_steps:
                lines.append(f"- {str(step).strip()}")
            lines.append("")
    else:
        summary_text = summary.summary_text or str(summary_body or "").strip()
        if summary_text:
            lines.append("## Overview")
            lines.append("")
            lines.append(summary_text)
            lines.append("")

    for section in sections:
        if not section.cards:
            continue
        lines.append(f"## {section.heading}")
        for card in section.cards:
            card_line = f"- **{card.title}** — {card.content}"
            lines.append(card_line.strip())
            if card.metadata:
                meta_tokens = []
                for key in ("date", "source", "page", "location", "person"):
                    value = card.metadata.get(key)
                    if value:
                        meta_tokens.append(f"{key.title()}: {value}")
                if meta_tokens:
                    lines.append(f"  - _{'; '.join(meta_tokens)}_")
        lines.append("")

    if images:
        lines.append("## Visual References")
        for image in images:
            url = image.local_path or image.url or image.source or ""
            if not url:
                continue
            alt = image.metadata.get("alt") or image.metadata.get("article_title") or (image.kind or "Article image")
            lines.append(f"![{alt}]({url})")
        lines.append("")

    return "\n".join(lines).strip()


@app.get("/api/brief/{article_id}", response_model=BriefResponse)
async def build_article_brief(
    request: Request,
    article_id: str,
    refresh: bool = Query(False, description="Force regeneration of stored cards"),
    refresh_summary: bool = Query(False, description="Regenerate narrative summary"),
    refresh_images: bool = Query(False, description="Re-fetch article imagery"),
    include_markdown: bool = Query(True, description="Include markdown representation of the brief"),
):
    """
    Aggregate cards, summaries, and imagery into a structured brief payload for an article.
    """
    metadata, cards, generated = await _load_pin_payload(request, article_id, refresh=refresh)

    summary_payload = await _build_card_summary(
        request,
        metadata,
        cards,
        refresh_summary=refresh or refresh_summary,
    )

    article_images: List[dict[str, Any]] = []
    image_sources = Counter()
    try:
        image_result = await refresh_article_images(
            article_id=article_id,
            request=request,
            force=refresh_images,
            allow_generation=True,
        )
        article_images = image_result.get("images", []) or []
        for img in article_images:
            image_sources[str(img.get("source") or "unknown")] += 1
    except Exception as image_err:
        logger.warning("Failed to refresh images for %s: %s", article_id, image_err)
        try:
            article_images = list_article_images(article_id, include_generated=True)
            for img in article_images:
                image_sources[str(img.get("source") or "cache")] += 1
        except Exception as list_err:
            logger.debug("Failed to load cached images for %s: %s", article_id, list_err)
            article_images = []

    brief_images: List[BriefImage] = []
    for img in article_images:
        url = img.get("local_path") or img.get("source_url") or img.get("source")
        brief_images.append(
            BriefImage(
                kind=img.get("kind"),
                source=img.get("source"),
                url=url,
                local_path=img.get("local_path"),
                width=img.get("width"),
                height=img.get("height"),
                generated=bool(img.get("generated")),
                metadata=img.get("metadata") or {},
            )
        )

    grouped_cards: Dict[str, List[Card]] = defaultdict(list)
    for card in cards:
        grouped_cards[card.type].append(card)

    def _section_heading(card_type: str) -> str:
        overrides = {
            "person": "People",
            "quote": "Quotes",
        }
        if not card_type:
            return "Cards"
        base = overrides.get(card_type, card_type.title())
        if card_type not in overrides and not base.endswith("s"):
            base = f"{base}s"
        return base

    card_type_sort_order = {
        "event": 0,
        "person": 1,
        "place": 2,
        "object": 3,
        "quote": 4,
    }
    sorted_groups = sorted(
        grouped_cards.items(),
        key=lambda item: (card_type_sort_order.get(item[0], 100), item[0]),
    )

    sections = [
        BriefSection(
            heading=_section_heading(card_type),
            card_type=card_type,
            cards=group,
        )
        for card_type, group in sorted_groups
    ]

    markdown = _render_brief_markdown(metadata, summary_payload, sections, brief_images) if include_markdown else ""

    return BriefResponse(
        article=metadata,
        summary=summary_payload,
        sections=sections,
        images=brief_images,
        markdown=markdown,
        generated_cards=generated,
        card_type_counts={card_type: len(group) for card_type, group in grouped_cards.items()},
        image_sources={source: count for source, count in image_sources.items() if count},
    )

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
    publication: Annotated[str | None, Query(description="Publication filter")] = None,
    people_orgs: Annotated[str | None, Query(description="People or organizations filter")] = None,
    keywords: Annotated[str | None, Query(description="Additional keywords filter")] = None,
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
    publication_clean = publication.strip() if publication and publication.strip() else None
    people_orgs_clean = people_orgs.strip() if people_orgs and people_orgs.strip() else None
    keywords_clean = keywords.strip() if keywords and keywords.strip() else None

    # Handle date range - add to query if specified
    # Trove API supports date range in query: date:[1800 TO 1900]
    query_terms: list[str] = []
    if q_clean:
        query_terms.append(q_clean)
    if keywords_clean:
        query_terms.append(keywords_clean.replace('"', '\\"'))
    if publication_clean:
        safe_publication = publication_clean.replace('"', '\\"')
        query_terms.append(f'title:"{safe_publication}"')
    if people_orgs_clean:
        safe_people = people_orgs_clean.replace('"', '\\"')
        query_terms.append(f'"{safe_people}"')
    if year_from or year_to:
        year_from_val = year_from if year_from else 1800
        year_to_val = year_to if year_to else 2024
        date_range = f"date:[{year_from_val} TO {year_to_val}]"
        query_terms.append(date_range)
    compiled_query = " ".join(term for term in query_terms if term).strip()

    # Calculate pagination
    can_paginate = category != "all"
    prev_s = max(0, s - n) if can_paginate else 0
    next_s = s + n if can_paginate else 0

    error_message = None
    items = []
    total = 0

    # Check if query is required but empty - show helpful error without making API call
    has_query_input = bool(
        q_clean
        or keywords_clean
        or publication_clean
        or people_orgs_clean
        or year_from
        or year_to
    )

    if not has_query_input and category in categories_requiring_query:
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
                q=compiled_query,
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
            "publication": publication_clean or "",
            "people_orgs": people_orgs_clean or "",
            "keywords": keywords_clean or "",
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
            query_params.append(f"q={quote_plus(q_clean)}")
        if category:
            query_params.append(f"category={category}")
        if year_from:
            query_params.append(f"year_from={year_from}")
        if year_to:
            query_params.append(f"year_to={year_to}")
        if l_place_clean:
            query_params.append(f"l_place={quote_plus(l_place_clean)}")
        if l_format_clean:
            query_params.append(f"l_format={quote_plus(l_format_clean)}")
        if publication_clean:
            query_params.append(f"publication={quote_plus(publication_clean)}")
        if people_orgs_clean:
            query_params.append(f"people_orgs={quote_plus(people_orgs_clean)}")
        if keywords_clean:
            query_params.append(f"keywords={quote_plus(keywords_clean)}")
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
            from app.archive_detective.router import _get_session_key
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
    from app.archive_detective.research_context import add_article_to_context
    
    # Fetch article - pass both ID and URL if available (URL helps with fetching)
    data = await fetch_item_text(id, trove_url=url)
    
    # If fetch failed but we have snippet/title from search results, use those
    if not data.get("ok"):
        if snippet or title:
            # Use search result data as fallback
            # Only show "Full text not available" message if we don't have a snippet
            fallback_text = snippet if snippet else "Full text not available. This article may only have a snippet available from the search results."
            data = {
                "ok": True,
                "id": id,
                "title": title or "Untitled Article",
                "date": date or "",
                "source": source or "",
                "url": url or "",
                "text": fallback_text,
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
    # Prefer full text from fetch_item_text over snippet
    if not data.get("text"):
        if data.get("snippet"):
            data["text"] = data["snippet"]
        elif snippet:
            data["text"] = snippet
        else:
            data["text"] = "No text content available for this article."
    
    # Use provided URL if available and not in data
    if url and not data.get("url"):
        data["url"] = url
    
    # Override with provided metadata if available (from search results), but only if data is missing
    if title and not data.get("title"):
        data["title"] = title
    if date and not data.get("date"):
        data["date"] = date
    if source and not data.get("source"):
        data["source"] = source
    
    # Don't override text with snippet if we already have full text
    # Only use snippet if we don't have any text
    if snippet and not data.get("text"):
        data["text"] = snippet

    normalized_id = normalize_trove_id(id)
    if not data.get("id"):
        data["id"] = normalized_id
    
    # Add article to research context for AI reference
    try:
        from app.archive_detective.research_context import add_article_to_context
        from app.archive_detective.router import _get_session_key
        session_key = _get_session_key(request)
        add_article_to_context(session_key, data)
    except Exception as ctx_err:
        logger.warning(f"Failed to add article to context: {ctx_err}")

    # Load stored imagery (and refresh if missing)
    article_images: list[dict[str, Any]] = []
    try:
        refresh_result = await refresh_article_images(
            article_id=id,
            request=request,
            force=False,
            allow_generation=True,
        )
        article_images = refresh_result.get("images", [])
    except Exception as image_err:
        logger.warning(f"Failed to refresh article images for {id}: {image_err}")
        try:
            from app.context_store import list_article_images

            article_images = list_article_images(id)
        except Exception as list_err:
            logger.debug(f"Failed to read cached images for {id}: {list_err}")

    primary_image = next((img for img in article_images if not img.get("generated")), None)
    if not primary_image and article_images:
        primary_image = article_images[0]

    if primary_image and not data.get("image_url"):
        primary_url = primary_image.get("local_path") or primary_image.get("source_url")
        if primary_url:
            data["image_url"] = primary_url
    
    context = {
        "request": request,
        "article": data,
        "article_images": article_images,
        "primary_image": primary_image,
        "article_id": normalized_id,
    }
    
    template = templates_env.get_template("reader.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/api/item/{item_id}")
async def get_item(item_id: str, request: Request, client: TroveClient = Depends(get_trove_client)):
    """Get item details for preview with enhanced metadata."""
    from app.archive_detective import fetch_item_text
    from app.archive_detective.research_context import add_article_to_context
    from app.services import TroveSearchService
    
    # Try to get URL from query params if provided
    trove_url = request.query_params.get("url")
    
    try:
        # First try: fetch full article text (best for newspapers)
        article_data = await fetch_item_text(item_id, trove_url=trove_url)
        if article_data.get("ok"):
            result = {
                "ok": True,
                "item": {
                    "id": article_data.get("id", item_id),
                    "title": article_data.get("title", "Untitled"),
                    "date": article_data.get("date", ""),
                    "source": article_data.get("source", ""),
                    "category": article_data.get("category", ""),
                    "page": article_data.get("page", ""),
                    "url": article_data.get("url", ""),
                    "image_url": article_data.get("image_url"),
                    "snippet": article_data.get("snippet", "") or (article_data.get("text", "")[:500] if article_data.get("text") else ""),
                    "text": article_data.get("text", ""),
                    "full_text": article_data.get("text", ""),
                    "text_length": len(article_data.get("text", "")),
                    "has_full_text": bool(article_data.get("text") and len(article_data.get("text", "")) > len(article_data.get("snippet", ""))),
                }
            }
            # Also return flat structure for backward compatibility
            result.update(result["item"])
            # Add to research context
            try:
                from app.archive_detective.research_context import add_article_to_context
                from app.archive_detective.router import _get_session_key
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
                        "category": item_data.get("category", ""),
                        "snippet": item_data.get("snippet", "")[:500] if item_data.get("snippet") else "",
                        "url": item_data.get("trove_url", ""),
                        "thumbnail": item_data.get("image_thumb"),
                        "image_full": item_data.get("image_full"),
                        "has_full_text": False,  # Search results don't have full text
                        "text_length": 0,
                    }
                    # Add to research context
                    try:
                        from app.archive_detective.research_context import add_article_to_context
                        from app.archive_detective.router import _get_session_key
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
            from app.archive_detective.research_context import add_article_to_context
            from app.archive_detective.router import _get_session_key
            session_key = _get_session_key(request)
            add_article_to_context(session_key, result)
    except Exception as ctx_err:
        logger.warning(f"Failed to add article to context: {ctx_err}")
    
    return result


@app.get("/api/collections")
async def get_collections(request: Request):
    """Get all collections for the session."""
    from app.context_store import sid_from, list_collections, get_collection_items
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collections = list_collections(sid)
    # Get item counts for each collection
    collections_with_counts = []
    for col in collections:
        items = get_collection_items(col["id"])
        collections_with_counts.append({
            **col,
            "item_count": len(items)
        })
    
    return {"ok": True, "collections": collections_with_counts}


@app.post("/api/collections")
async def create_collection(request: Request, body: dict = Body(...)):
    """Create a new collection."""
    from app.context_store import sid_from, create_collection
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    name = body.get("name", "Untitled Collection")
    description = body.get("description", "")
    color = body.get("color", "#3b82f6")
    
    result = create_collection(sid, name, description, color)
    return result


@app.get("/api/collections/{collection_id}")
async def get_collection_endpoint(request: Request, collection_id: str):
    """Get a collection with its items."""
    from app.context_store import sid_from, get_collection as get_collection_db, get_collection_items
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collection = get_collection_db(collection_id)
    if not collection or collection["sid"] != sid:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    items = get_collection_items(collection_id)
    return {
        "ok": True,
        "collection": collection,
        "items": items
    }


@app.put("/api/collections/{collection_id}")
async def update_collection_endpoint(request: Request, collection_id: str, body: dict = Body(...)):
    """Update a collection."""
    from app.context_store import sid_from, get_collection as get_collection_db, update_collection
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collection = get_collection_db(collection_id)
    if not collection or collection["sid"] != sid:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    update_collection(
        collection_id,
        name=body.get("name"),
        description=body.get("description"),
        color=body.get("color")
    )
    return {"ok": True, "message": "Collection updated"}


@app.delete("/api/collections/{collection_id}")
async def delete_collection_endpoint(request: Request, collection_id: str):
    """Delete a collection."""
    from app.context_store import sid_from, get_collection as get_collection_db, delete_collection
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collection = get_collection_db(collection_id)
    if not collection or collection["sid"] != sid:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    delete_collection(collection_id)
    return {"ok": True, "message": "Collection deleted"}


@app.post("/api/collections/{collection_id}/items")
async def add_item_to_collection_endpoint(request: Request, collection_id: str, body: dict = Body(...)):
    """Add an item to a collection."""
    from app.context_store import sid_from, get_collection as get_collection_db, add_item_to_collection
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collection = get_collection_db(collection_id)
    if not collection or collection["sid"] != sid:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    trove_id = body.get("trove_id") or body.get("item_id")
    if not trove_id:
        raise HTTPException(status_code=400, detail="trove_id required")
    
    notes = body.get("notes", "")
    add_item_to_collection(collection_id, str(trove_id), notes)
    return {"ok": True, "message": "Item added to collection"}


@app.delete("/api/collections/{collection_id}/items/{trove_id}")
async def remove_item_from_collection_endpoint(request: Request, collection_id: str, trove_id: str):
    """Remove an item from a collection."""
    from app.context_store import sid_from, get_collection as get_collection_db, remove_item_from_collection
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    collection = get_collection_db(collection_id)
    if not collection or collection["sid"] != sid:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    remove_item_from_collection(collection_id, trove_id)
    return {"ok": True, "message": "Item removed from collection"}


@app.post("/api/collections/add")
async def add_to_collection(body: dict = Body(...)):
    """Add item to collection (legacy endpoint for backward compatibility)."""
    # For backward compatibility - redirects to new endpoint
    # This would need collection_id, but we'll create a default one if needed
    return {"ok": True, "message": "Use POST /api/collections/{collection_id}/items instead"}


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
async def add_note(request: Request, body: dict = Body(...)):
    """Add note to collection."""
    from app.context_store import sid_from, add_note as store_note
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    article_id = body.get("article_id") or body.get("trove_id")
    note_text = body.get("text", "")
    note_type = body.get("type", "note")  # note, highlight, annotation
    
    if article_id and note_text:
        store_note(sid, article_id, note_text, note_type=note_type)
        return {"ok": True, "message": "Note added"}
    
    return {"ok": False, "error": "Missing article_id or note text"}


@app.get("/api/notes/{article_id}")
async def get_notes(request: Request, article_id: str):
    """Get notes for an article."""
    from app.context_store import sid_from, get_notes_for_article
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    notes = get_notes_for_article(sid, article_id)
    return {"ok": True, "notes": notes}


@app.delete("/api/notes/{note_id}")
async def delete_note(request: Request, note_id: str):
    """Delete a note."""
    from app.context_store import sid_from, delete_note as store_delete_note
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    store_delete_note(sid, note_id)
    return {"ok": True, "message": "Note deleted"}


@app.get("/iiif/manifest/{article_id}")
async def get_iiif_manifest(request: Request, article_id: str):
    """Get IIIF manifest for an article."""
    from app.iiif import generate_iiif_manifest, get_trove_image_urls
    from app.archive_detective import fetch_item_text
    
    # Fetch article data
    data = await fetch_item_text(article_id)
    
    title = data.get("title", "Untitled Article")
    image_url = data.get("image_url")
    article_url = data.get("url")
    
    # If no image_url but we have article_url, try to generate image URLs
    if not image_url and article_url:
        image_urls = get_trove_image_urls(article_url, article_id)
        if image_urls:
            image_url = image_urls[0]  # Use first (highest quality)
    
    # Get base URL from request
    base_url = str(request.base_url).rstrip("/")
    
    manifest = generate_iiif_manifest(
        article_id=article_id,
        title=title,
        image_url=image_url,
        article_url=article_url,
        base_url=base_url,
    )
    
    return manifest


@app.post("/api/article/{article_id}/summarize")
async def summarize_article(
    request: Request, article_id: str, payload: dict | None = Body(default=None)
):
    """Generate AI summary of an article."""
    from app.archive_detective import fetch_item_text
    from app.archive_detective.summarize import summarize_text
    
    fallback_text = ""
    incoming_metadata: dict[str, str] = {}
    if payload:
        fallback_text = (
            payload.get("fallback_text")
            or payload.get("text")
            or payload.get("snippet")
            or ""
        )
        fallback_text = fallback_text.strip()
        raw_meta = payload.get("metadata")
        if isinstance(raw_meta, dict):
            incoming_metadata = {
                key: (value.strip() if isinstance(value, str) else value)
                for key, value in raw_meta.items()
                if value
            }

    query_meta = {
        "title": request.query_params.get("title"),
        "date": request.query_params.get("date"),
        "source": request.query_params.get("source"),
        "page": request.query_params.get("page"),
    }
    for key, value in query_meta.items():
        if value and key not in incoming_metadata:
            incoming_metadata[key] = value.strip()
    
    # Fetch full text
    data = await fetch_item_text(article_id)
    
    if not data.get("ok"):
        if not fallback_text:
            return {"ok": False, "error": "Could not fetch article"}
        text = fallback_text
    else:
        text = data.get("text") or data.get("snippet", "")
        if not text and fallback_text:
            text = fallback_text
    
    if not text:
        return {"ok": False, "error": "No text available to summarize"}
    
    # Generate summary
    metadata = {
        "title": incoming_metadata.get("title")
        or data.get("title")
        or "Untitled",
        "date": incoming_metadata.get("date") or data.get("date"),
        "source": incoming_metadata.get("source") or data.get("source"),
        "page": incoming_metadata.get("page") or data.get("page"),
    }

    summary_result = summarize_text(text, use_llm=True, metadata=metadata)
    
    return {
        "ok": True,
        "summary": summary_result.get("summary", ""),
        "bullets": summary_result.get("bullets", []),
        "article_id": article_id,
        "title": metadata["title"],
        "date": metadata.get("date"),
        "source": metadata.get("source"),
        "page": metadata.get("page"),
        "metadata": metadata,
    }


@app.post("/api/article/{article_id}/condense")
async def condense_article_summary(
    article_id: str, payload: dict | None = Body(default=None)
):
    """Condense an existing summary into a shorter Aussie-voiced version."""
    from app.archive_detective.summarize import condense_summary

    payload = payload or {}
    summary = (payload.get("summary") or "").strip()
    bullets = payload.get("bullets") or []

    if not summary and not bullets:
        raise HTTPException(
            status_code=400, detail="No summary or bullets supplied to condense."
        )

    if not isinstance(bullets, list):
        bullets = []

    raw_meta = payload.get("metadata")
    metadata = (
        {
            key: (value.strip() if isinstance(value, str) else value)
            for key, value in raw_meta.items()
            if value
        }
        if isinstance(raw_meta, dict)
        else {}
    )

    condensed_result = condense_summary(
        summary=summary,
        bullets=bullets,
        use_llm=True,
        metadata=metadata,
    )
    condensed_text = (condensed_result.get("condensed") or "").strip()

    if not condensed_text:
        return {"ok": False, "error": "Failed to condense summary"}

    return {
        "ok": True,
        "condensed": condensed_text,
        "article_id": article_id,
    }


@app.get("/api/article/{article_id}/images")
async def get_article_images(article_id: str, include_generated: bool = True):
    """Return stored imagery metadata for an article."""
    from app.context_store import list_article_images

    images = list_article_images(article_id, include_generated=include_generated)
    return {
        "ok": True,
        "article_id": article_id,
        "images": images,
        "count": len(images),
    }


@app.post("/api/article/{article_id}/images/sync")
async def sync_article_images(
    request: Request,
    article_id: str,
    payload: dict | None = Body(default=None),
):
    """
    Refresh article imagery by harvesting Trove assets and optional fallbacks.
    """
    from app.services import refresh_article_images

    options = payload or {}
    force = bool(options.get("force"))
    allow_generation = bool(options.get("allow_generation"))
    priorities = options.get("priorities") or []
    if isinstance(priorities, str):
        priorities = [priorities]

    result = await refresh_article_images(
        article_id=article_id,
        request=request,
        force=force,
        allow_generation=allow_generation,
        priorities=priorities,
    )

    return {
        "ok": True,
        "article_id": article_id,
        **result,
    }


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


@app.get("/api/report/sources")
async def get_report_sources(request: Request):
    """Get pinned articles for Report Studio sources panel."""
    from app.context_store import sid_from, list_pinned_articles
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    pinned = list_pinned_articles(sid)
    return {
        "ok": True,
        "sources": [
            {
                "id": item["trove_id"],
                "title": item["title"] or "Untitled",
                "date": item["date"] or "",
                "source": item["source"] or "",
                "url": item["url"] or "",
                "snippet": item["snippet"] or ""
            }
            for item in pinned
        ]
    }


@app.post("/api/report/synthesize")
async def synthesize_report(request: Request, body: dict = Body(...)):
    """Use AI to synthesize report from pinned articles and draft content."""
    from app.context_store import sid_from, list_pinned_articles, pack_for_prompt
    from app.archive_detective import chat_llm
    from app.utils.errors import user_friendly_openai_error
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    draft_content = body.get("content", "")
    if not draft_content.strip():
        return {"ok": False, "error": "No content provided"}
    
    # Get pinned articles context
    pinned = list_pinned_articles(sid)
    context_pack = pack_for_prompt(sid, max_chars=3000)
    
    # Build synthesis prompt - be explicit that we want the enhanced report
    prompt = f"""You are a research assistant helping to enhance a research report. The user has drafted this report:

{draft_content}

They have {len(pinned)} pinned sources available. Your task is to synthesize and enhance this report by:
1. Improving clarity and flow
2. Adding relevant citations from the pinned sources (use [citation] format)
3. Ensuring the report is well-structured
4. Maintaining the user's original intent and voice

IMPORTANT: Return ONLY the enhanced report text. Do not include explanations, apologies, or meta-commentary. Just return the improved report text directly."""
    
    if not chat_llm.is_enabled():
        return {"ok": False, "error": "AI chat is not enabled. Configure OPENAI_API_KEY."}
    
    try:
        # Use chat LLM to synthesize
        response = chat_llm.route_message(
            prompt,
            context=context_pack["text"],
            use_function_calling=False
        )
        
        if response and "say" in response:
            synthesized = response["say"]
            return {
                "ok": True,
                "synthesized": synthesized,
                "sources_used": len(pinned)
            }
        else:
            return {"ok": False, "error": "AI synthesis failed"}
    except Exception as e:
        logger.exception(f"Error synthesizing report: {e}")
        # Use friendly error mapping
        try:
            raise user_friendly_openai_error(e)
        except HTTPException as http_err:
            return {"ok": False, "error": http_err.detail}


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


@app.get("/fishing", response_class=HTMLResponse)
async def fishing_page(request: Request):
    """Fishing page with map and species display."""
    context = {
        "request": request,
    }
    template = templates_env.get_template("fishing.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/api/fishing/species")
async def get_fishing_species(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    client: TroveClient = Depends(get_trove_client),
):
    """Search Trove for fish species data by location."""
    from app.services import TroveSearchService
    import httpx
    
    try:
        # Reverse geocode to get location name (optional, but helpful)
        location_name = None
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={
                        "format": "json",
                        "lat": lat,
                        "lon": lon,
                        "zoom": 10,
                        "addressdetails": 1,
                    },
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    # Extract location name - prioritize Australian locations
                    address = data.get("address", {})
                    parts = []
                    
                    # For Australian locations, prioritize city/town names
                    if address.get("city"):
                        parts.append(address["city"])
                    elif address.get("town"):
                        parts.append(address["town"])
                    elif address.get("village"):
                        parts.append(address["village"])
                    elif address.get("suburb"):
                        parts.append(address["suburb"])
                    elif address.get("locality"):
                        parts.append(address["locality"])
                    
                    # Add state/region for context
                    if address.get("state"):
                        parts.append(address["state"])
                    elif address.get("region"):
                        parts.append(address["region"])
                    elif address.get("state_district"):
                        parts.append(address["state_district"])
                    
                    # For Australian states, use proper format
                    if parts:
                        location_name = ", ".join(parts)
                        # Clean up common Australian state abbreviations
                        location_name = location_name.replace("NSW", "New South Wales")
                        location_name = location_name.replace("VIC", "Victoria")
                        location_name = location_name.replace("QLD", "Queensland")
                        location_name = location_name.replace("SA", "South Australia")
                        location_name = location_name.replace("WA", "Western Australia")
                        location_name = location_name.replace("TAS", "Tasmania")
                        location_name = location_name.replace("NT", "Northern Territory")
                        location_name = location_name.replace("ACT", "Australian Capital Territory")
                    else:
                        # Fallback to display name
                        display_name = data.get("display_name", "")
                        if display_name:
                            # Take first meaningful part (usually city/town)
                            parts = [p.strip() for p in display_name.split(",")]
                            location_name = parts[0] if parts else None
                        else:
                            location_name = None
        except Exception as e:
            logger.warning(f"Reverse geocoding failed: {e}")
        
        # Search Trove for fish species mentions in this location
        # We'll search for various fish-related terms combined with location
        service = TroveSearchService(client)
        
        # Build search query - search for fishing/fish species in this area
        # Trove works better with location names rather than coordinates
        # Extract state/region for broader searches if city not found
        state_name = None
        if location_name:
            # Try to extract state from location name
            location_parts = location_name.split(",")
            if len(location_parts) > 1:
                state_name = location_parts[-1].strip()
        
        if location_name:
            # Use location name in searches - try both full name and city/state separately
            city_part = location_name.split(",")[0].strip() if "," in location_name else location_name
            queries = [
                f'fishing AND "{city_part}"',
                f'fish AND "{city_part}"',
                f'fishery AND "{city_part}"',
                f'"fish species" AND "{city_part}"',
                f'angling AND "{city_part}"',
            ]
            # If we have state, also try state-level searches
            if state_name and state_name != city_part:
                queries.extend([
                    f'fishing AND "{state_name}"',
                    f'fish AND "{state_name}"',
                ])
            place_filter = location_name
        else:
            # Without location name, search more broadly for fishing content
            queries = [
                "fishing",
                "fish species",
                "fishery",
                "marine life",
            ]
            place_filter = None
        
        all_species = []
        seen_titles = set()
        
        # Try each query
        for query in queries:
            try:
                records, _ = await service.search(
                    q=query,
                    category="all",
                    n=10,
                    s=0,
                    l_place=place_filter,
                )
                
                # Process records to extract species information
                for record in records:
                    # Create a unique key to avoid duplicates
                    title_key = (record.title or "").lower().strip()
                    if title_key and title_key not in seen_titles:
                        seen_titles.add(title_key)
                        
                        # Extract potential species name from title or snippet
                        species_name = extract_species_name(record.title or "", record.snippet or "")
                        
                        # Only include if it seems fish-related
                        if is_fish_related(record.title or "", record.snippet or ""):
                            all_species.append({
                                "species_name": species_name,
                                "title": record.title,
                                "date": record.issued,
                                "source": record.publisher_or_source,
                                "snippet": record.snippet,
                                "trove_url": record.trove_url,
                                "image_thumb": record.image_thumb,
                                "image_full": record.image_full,
                            })
            except Exception as e:
                logger.warning(f"Search query failed: {query}, error: {e}")
                continue
        
        # Limit to top 20 results
        all_species = all_species[:20]
        
        return {
            "ok": True,
            "species": all_species,
            "location": {
                "lat": lat,
                "lng": lon,
                "name": location_name,
            },
            "count": len(all_species),
        }
        
    except Exception as e:
        logger.error(f"Error fetching fishing species: {e}")
        return {
            "ok": False,
            "error": str(e),
            "species": [],
            "location": {"lat": lat, "lng": lon, "name": None},
        }


def extract_species_name(title: str, snippet: str) -> str:
    """Extract fish species name from title or snippet."""
    import re
    
    # Common Australian fish species (including multi-word names)
    common_species = [
        "barramundi", "black bream", "yellowfin bream", "bream", 
        "flathead", "dusky flathead", "tiger flathead",
        "snapper", "pink snapper", "whiting", "king george whiting",
        "tailor", "blue tailor", "mulloway", "jewfish", "trevally",
        "kingfish", "yellowtail kingfish", "salmon", "atlantic salmon",
        "tuna", "yellowfin tuna", "bluefin tuna", "mackerel", "spanish mackerel",
        "garfish", "sea garfish", "bass", "australian bass", "perch",
        "murray cod", "cod", "trout", "rainbow trout", "brown trout", "eel",
        "prawn", "king prawn", "crab", "blue swimmer crab", "mud crab",
        "lobster", "rock lobster", "oyster", "mussel", "abalone",
        "octopus", "squid", "calamari", "flathead", "whiting",
    ]
    
    text = (title + " " + snippet).lower()
    
    # Look for species names (check longest matches first)
    species_matches = []
    for species in sorted(common_species, key=len, reverse=True):
        if species.lower() in text:
            # Find the position to prefer earlier mentions
            pos = text.find(species.lower())
            species_matches.append((pos, species))
    
    if species_matches:
        # Return the first (earliest) match, capitalized properly
        _, species = min(species_matches, key=lambda x: x[0])
        # Capitalize each word
        return " ".join(word.capitalize() for word in species.split())
    
    # Try to extract from patterns like "fishing for X" or "X caught"
    patterns = [
        r'fishing for ([a-z]+(?:\s+[a-z]+)?)',
        r'caught.*?([a-z]+(?:\s+[a-z]+)?)\s+(?:weigh|pound|kg)',
        r'([a-z]+(?:\s+[a-z]+)?)\s+(?:fish|species)',
        r'([a-z]+(?:\s+[a-z]+)?)\s+caught',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            potential = match.group(1).strip()
            # Filter out common words that aren't species names
            skip_words = ["the", "a", "an", "and", "or", "but", "for", "with", "from"]
            words = potential.split()
            if words and words[0].lower() not in skip_words:
                if len(potential) > 2 and len(words) <= 3:
                    return potential.title()
    
    # Fallback: use first few words of title if it seems relevant
    title_words = title.split()[:4]
    # Remove common stop words
    filtered_words = [w for w in title_words if w.lower() not in ["the", "a", "fishing", "fish", "for", "and"]]
    if filtered_words and len(filtered_words[0]) > 3:
        return " ".join(filtered_words[:3])
    
    return "Fish species"


def is_fish_related(title: str, snippet: str) -> bool:
    """Check if a record is related to fish or fishing."""
    fish_keywords = [
        "fish", "fishing", "fisherman", "fishermen", "fishery", "fisheries",
        "angler", "angling", "catch", "caught", "marine", "seafood",
        "barramundi", "bream", "snapper", "whiting", "salmon", "tuna",
        "prawn", "crab", "lobster", "oyster", "mussel", "abalone",
    ]
    
    text = (title + " " + snippet).lower()
    
    return any(keyword in text for keyword in fish_keywords)


@app.get("/api/timeline")
async def api_timeline():
    """API endpoint for timeline data."""
    return {"ok": True, "events": []}


@app.get("/api/tunnel/status")
async def get_tunnel_status():
    """Check if ngrok tunnel is active for this server."""
    # Try pyngrok first (most reliable if installed)
    try:
        from pyngrok import ngrok
        tunnels = ngrok.get_tunnels()
        if tunnels:
            # Find HTTP tunnel (not HTTPS)
            http_tunnel = next((t for t in tunnels if t.proto == "http"), None)
            if http_tunnel:
                return {"ok": True, "url": http_tunnel.public_url}
            # Fallback to any tunnel
            if tunnels:
                return {"ok": True, "url": tunnels[0].public_url}
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback: check ngrok local API (works if ngrok is running separately)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                http_tunnels = [t for t in tunnels if t.get("proto") == "http"]
                if http_tunnels:
                    return {"ok": True, "url": http_tunnels[0].get("public_url")}
    except Exception:
        pass
    
    return {"ok": False, "url": None, "message": "No tunnel active. Click 'Start Tunnel' to create one."}


@app.post("/api/tunnel/start")
async def start_tunnel():
    """Start (or restart) an ngrok tunnel for this server with updated status."""
    try:
        from pyngrok import conf, exception, ngrok
    except ImportError:
        return {
            "ok": False,
            "error": "pyngrok not installed",
            "message": (
                "Install pyngrok: pip install pyngrok\n"
                "Or run ngrok manually: ngrok http 8000"
            ),
        }

    port = int(os.getenv("PORT", "8000"))
    authtoken = (
        os.getenv("NGROK_AUTHTOKEN")
        or os.getenv("NGROK_TOKEN")
        or os.getenv("NGROK_AUTH_TOKEN")
    )
    region = os.getenv("NGROK_REGION")

    try:
        default_conf = conf.get_default()
        if authtoken:
            default_conf.auth_token = authtoken
        elif not default_conf.auth_token and not Path.home().joinpath(".ngrok2", "ngrok.yml").exists():
            return {
                "ok": False,
                "error": "ngrok authtoken missing",
                "message": (
                    "ngrok authtoken is required. "
                    "Set NGROK_AUTHTOKEN environment variable or run "
                    "'ngrok config add-authtoken <your-token>'."
                ),
            }
    except Exception as cfg_error:
        logger.exception("Failed to configure ngrok authtoken")
        return {
            "ok": False,
            "error": str(cfg_error),
            "message": "Failed to configure ngrok authtoken.",
        }

    try:
        # Disconnect any existing tunnels bound to this port to ensure a clean restart
        existing_tunnels = ngrok.get_tunnels()
        for tunnel in existing_tunnels:
            addr = tunnel.config.get("addr")
            if addr and str(port) in addr:
                try:
                    ngrok.disconnect(tunnel.public_url)
                except exception.PyngrokNgrokError:
                    # Ignore disconnect errors and continue
                    pass

        connect_kwargs = {"proto": "http"}
        if region:
            connect_kwargs["options"] = {"region": region}

        tunnel = ngrok.connect(port, **connect_kwargs)

        return {
            "ok": True,
            "url": tunnel.public_url,
            "message": "Tunnel started successfully",
        }
    except exception.PyngrokNgrokError as pyngrok_error:
        logger.exception("pyngrok error while starting tunnel")
        return {
            "ok": False,
            "error": str(pyngrok_error),
            "message": (
                "Failed to start tunnel via ngrok. "
                "Check tunnel limits or run 'pkill ngrok' to clear stale sessions."
            ),
        }
    except Exception as e:
        logger.exception("Failed to start tunnel")
        return {
            "ok": False,
            "error": str(e),
            "message": "Failed to start tunnel. Make sure ngrok is installed and configured.",
        }


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
    """Generate QR code for web app URL."""
    if not url:
        # Check for tunnel first (preferred)
        tunnel_status = await get_tunnel_status()
        if tunnel_status.get("ok") and tunnel_status.get("url"):
            url = tunnel_status["url"]
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
                    hostname = "127.0.0.1"
            
            port = request.url.port or 8000
            url = f"http://{hostname}:{port}"
    
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


@app.get("/apps/api", response_class=HTMLResponse)
async def apps_api_hub(request: Request):
    """Hub page for Mobile API app - redirects to API app if running, otherwise shows info."""
    import socket
    
    api_port = int(os.getenv("API_PORT", "8001"))
    api_host = "127.0.0.1"
    
    # Check if API is running
    api_running = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((api_host, api_port))
        sock.close()
        api_running = (result == 0)
    except Exception:
        api_running = False
    
    # Get base URL for API
    base_url = f"{request.url.scheme}://{request.url.hostname}"
    if request.url.port:
        base_url += f":{request.url.port}"
    api_url = f"http://{api_host}:{api_port}"
    
    context = {
        "request": request,
        "api_running": api_running,
        "api_url": api_url,
        "api_port": api_port,
    }
    
    template = templates_env.get_template("apps_api_hub.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/apps/mobile", response_class=HTMLResponse)
async def apps_mobile_info(request: Request):
    """Info page for Mobile app with setup instructions."""
    import socket
    
    # Get API URL (default to port 8001)
    api_port = int(os.getenv("API_PORT", "8001"))
    api_host = "127.0.0.1"
    api_url = f"http://{api_host}:{api_port}"
    
    # Try to get local network IP
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    
    api_url_lan = f"http://{local_ip}:{api_port}"
    
    context = {
        "request": request,
        "api_url": api_url,
        "api_url_lan": api_url_lan,
        "api_port": api_port,
    }
    
    template = templates_env.get_template("apps_mobile_info.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/kingfisher", response_class=HTMLResponse)
async def kingfisher_page(request: Request):
    """Kingfisher - Lesson Cards Creator."""
    from app.context_store import sid_from, list_lesson_cards
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    cards = list_lesson_cards(sid)
    
    # Get unique categories
    categories = sorted(set(card.get("category", "") for card in cards if card.get("category")))
    
    context = {
        "request": request,
        "cards": cards,
        "categories": categories,
    }
    
    template = templates_env.get_template("kingfisher.html")
    return HTMLResponse(content=template.render(**context))


@app.get("/kingfisher/test-interface")
async def kingfisher_test_interface():
    """Serve the Kingfisher feature pack test page for manual card extraction checks."""
    test_file = Path(__file__).resolve().parent.parent / "backend" / "test_feature_pack.html"
    if test_file.exists():
        return FileResponse(test_file)
    raise HTTPException(status_code=404, detail="Kingfisher test interface not found")

@app.get("/api/lesson-cards")
async def get_lesson_cards(request: Request, category: str = Query(None)):
    """Get all lesson cards for the session."""
    from app.context_store import sid_from, list_lesson_cards
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    cards = list_lesson_cards(sid, category=category)
    return {"ok": True, "cards": cards}


@app.post("/api/lesson-cards")
async def create_lesson_card_endpoint(request: Request, body: dict = Body(...)):
    """Create a new lesson card."""
    from app.context_store import sid_from, create_lesson_card
    
    sid = sid_from(
        dict(request.headers),
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", "")
    )
    
    card = create_lesson_card(
        sid=sid,
        title=body.get("title", "Untitled Card"),
        front_text=body.get("front_text", ""),
        back_text=body.get("back_text", ""),
        category=body.get("category", ""),
        tags=body.get("tags", [])
    )
    
    return {"ok": True, "card": card}


@app.get("/api/lesson-cards/{card_id}")
async def get_lesson_card_endpoint(request: Request, card_id: str):
    """Get a specific lesson card."""
    from app.context_store import get_lesson_card
    
    card = get_lesson_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    return {"ok": True, "card": card}


@app.put("/api/lesson-cards/{card_id}")
async def update_lesson_card_endpoint(request: Request, card_id: str, body: dict = Body(...)):
    """Update a lesson card."""
    from app.context_store import update_lesson_card, get_lesson_card
    
    update_lesson_card(
        card_id=card_id,
        title=body.get("title"),
        front_text=body.get("front_text"),
        back_text=body.get("back_text"),
        category=body.get("category"),
        tags=body.get("tags")
    )
    
    card = get_lesson_card(card_id)
    return {"ok": True, "card": card}


@app.delete("/api/lesson-cards/{card_id}")
async def delete_lesson_card_endpoint(request: Request, card_id: str):
    """Delete a lesson card."""
    from app.context_store import delete_lesson_card
    
    delete_lesson_card(card_id)
    return {"ok": True, "message": "Card deleted"}
