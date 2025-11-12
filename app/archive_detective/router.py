from __future__ import annotations


import csv

import io

import os

import re

import zipfile

from datetime import datetime

from pathlib import Path

from typing import Any


try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from backports.zoneinfo import ZoneInfo


from fastapi import APIRouter, Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# Import template environment - using lazy import to avoid circular dependency
def get_templates_env():
    """Get the template environment from main module."""
    from app.main import templates_env
    return templates_env


from . import agent, chat_llm
from .article_io import extract_article_id_from_url, fetch_item_text
from .research_context import (
    add_article_to_context,
    format_context_for_llm,
    get_research_context,
    clear_context,
)


# Import search suggestions function
try:
    from .search_suggestions import _generate_search_suggestions
except ImportError:
    # Fallback if module not available
    async def _generate_search_suggestions(topic: str, recent_results: list[Any]) -> list[str]:
        return []


from .config import (
    APP_TITLE,
    ARCHIVE_DETECTIVE_ENABLED,
    DOCS_DIR,
    OUTPUTS_DIR,
    QUERIES_DIR,
    ensure_dirs,
)


from .image_fetcher import fetch_and_save_slnsw_image
from .report_builder import add_item, clear_report, load_report, make_pdf
from .summarize import summarize_text


# Import Trove search capability (imported inside /search handler when needed)
# from app.services import TroveSearchService


router = APIRouter()


# Simple in-memory storage for recent search results (session-based)
# In production, use proper session storage or Redis
_recent_searches: dict[str, list[Any]] = {}
_recent_search_records: dict[str, list[Any]] = {}



def _get_session_key(request: Request) -> str:

    """Get session key from request (simplified - use actual session in production)."""

    # Use client IP + user agent as session identifier

    # In production, use proper session management

    client_ip = request.client.host if request.client else "unknown"

    user_agent = request.headers.get("user-agent", "unknown")[:50]

    return f"{client_ip}:{user_agent}"



class ChatIn(BaseModel):
    message: str
    article_ids: list[str] | None = None  # Optional: article IDs to include in context



class TimelineRowIn(BaseModel):

    date: str

    owner: str

    role: str

    volume_folio: str = ""

    dealing: str = ""

    source: str = ""

    url: str = ""

    notes: str = ""



class TimelineUpdateIn(BaseModel):

    rows: list[dict[str, Any]]



@router.get("/chat", response_class=HTMLResponse)

async def chat_page(request: Request):

    templates_env = get_templates_env()

    template = templates_env.get_template("chat.html")

    html = template.render(request=request, app_title=APP_TITLE)

    return HTMLResponse(content=html)



def _ok(reply: str, file_path: str | None = None):
    payload = {"ok": True, "reply": reply, "say": reply}
    
    if file_path:
        payload["file"] = file_path
    
    return JSONResponse(payload)



@router.post("/api/chat")
async def chat(inbody: ChatIn, request: Request):
    try:
        msg = inbody.message.strip()
        session_key = _get_session_key(request)
        
        # If article_ids provided, ensure they're in context
        if inbody.article_ids:
            # Fetch and add articles to context
            from .article_io import fetch_item_text
            for article_id in inbody.article_ids[:10]:  # Limit to 10
                try:
                    data = await fetch_item_text(article_id)
                    if data.get("ok"):
                        add_article_to_context(session_key, data)
                except Exception as e:
                    logger.warning(f"Failed to fetch article {article_id} for context: {e}")

        # Slash commands (deterministic)
        if msg.startswith("/"):
            parts = msg.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            try:
                if cmd == "/generate-queries":
                    path = agent.cmd_generate_queries()
                    web = f"/files/queries/{os.path.basename(path)}"
                    return _ok(f"✅ Generated Trove CSV queries at {path}", web)

                elif cmd == "/make-brief":
                    path = agent.cmd_make_brief()
                    web = f"/files/docs/{os.path.basename(path)}"
                    return _ok(f"✅ Created brief template at {path}", web)

                elif cmd == "/harvest-stub":
                    res = agent.cmd_harvest_stub()
                    return _ok(res)

                elif cmd == "/report":
                    path = agent.cmd_report()
                    web = f"/files/outputs/{os.path.basename(path)}"
                    return _ok(f"✅ Composed placeholder report at {path}", web)

                elif cmd == "/read":
                    if not args:
                        return JSONResponse({"ok": False, "error": "Please provide article ID or URL"}, status_code=400)
                    from .article_io import extract_article_id_from_url, fetch_item_text
                    article_id = extract_article_id_from_url(args) or args
                    data = await fetch_item_text(article_id)
                    if data.get("ok"):
                        # Add to research context
                        add_article_to_context(session_key, data)
                        return _ok(f"📖 Article: {data.get('title', 'Untitled')}\n\n{data.get('text', data.get('snippet', ''))[:500]}")
                    else:
                        return JSONResponse({"ok": False, "error": data.get("error", "Failed to fetch article")}, status_code=500)

                elif cmd == "/search":
                    if not args:
                        return JSONResponse({"ok": False, "error": "Please provide a search query"}, status_code=400)
                    # Redirect to search page with query
                    return JSONResponse({
                        "ok": True,
                        "reply": f"Searching for: {args}",
                        "redirect": f"/search?q={args}"
                    })

                elif cmd == "/suggest-searches":
                    if not args:
                        return JSONResponse({"ok": False, "error": "Please provide a topic"}, status_code=400)
                    from .search_suggestions import _generate_search_suggestions
                    suggestions = await _generate_search_suggestions(args, [])
                    if suggestions:
                        return _ok(f"🔍 Search suggestions for '{args}':\n\n" + "\n".join(f"- {s}" for s in suggestions[:10]))
                    else:
                        return _ok(f"💡 Try searching for: {args}")

                elif cmd == "/summarize":
                    if not args:
                        return JSONResponse({"ok": False, "error": "Please provide text or article ID"}, status_code=400)
                    from .summarize import summarize_text
                    summary = await summarize_text(args)
                    return _ok(f"📝 Summary:\n\n{summary}")

                elif cmd == "/cite":
                    if not args:
                        return JSONResponse({"ok": False, "error": "Please provide article ID or URL"}, status_code=400)
                    from .article_io import extract_article_id_from_url, fetch_item_text
                    from ..context_store import pack_for_prompt
                    article_id = extract_article_id_from_url(args) or args
                    data = await fetch_item_text(article_id)
                    if data.get("ok"):
                        # Add to research context
                        add_article_to_context(session_key, data)
                        # Pin it for prominent citation
                        from ..context_store import set_pinned
                        set_pinned(session_key, str(data.get("id") or article_id), True)
                        # Get packed context to show what's available
                        packed = pack_for_prompt(session_key, max_chars=1000)
                        return _ok(f"📌 Pinned and cited: {data.get('title', 'Untitled')}\n\nContext now includes:\n{packed['text'][:500]}...")
                    else:
                        return JSONResponse({"ok": False, "error": data.get("error", "Failed to fetch article")}, status_code=500)

                elif cmd == "/help":
                    return _ok("""
Available commands:
/search <query> - Search Trove archives
/suggest-searches <topic> - Get search suggestions
/read <id_or_url> - Read an article
/cite <id_or_url> - Pin and cite an article (adds to context)
/summarize <text_or_id> - Summarize text
/add-to-report <id> - Add to report
/report-view - View report
/report-pdf - Generate PDF
/generate-queries - Generate CSV queries
/make-brief - Create brief template
/harvest-stub - Create timeline stub
/report - Generate report
/help - Show this help
                    """)

                else:
                    return JSONResponse({"ok": False, "error": f"Unknown command: {cmd}. Type /help for available commands."}, status_code=400)

            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception(f"Command error: {e}")
                return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
        else:
            # Non-slash command - check for timeline/entity queries first
            msg_lower = msg.lower()
            
            # Timeline-aware query detection (before LLM routing)
            try:
                # 1. Compare queries: "compare X vs Y" or "compare X and Y"
                if ("compare" in msg_lower and (" vs " in msg_lower or " and " in msg_lower or " with " in msg_lower)):
                    # Extract terms
                    compare_text = msg_lower.replace("compare", "").strip()
                    if " vs " in compare_text:
                        parts = compare_text.split(" vs ")
                    elif " and " in compare_text:
                        parts = compare_text.split(" and ")
                    elif " with " in compare_text:
                        parts = compare_text.split(" with ")
                    else:
                        parts = [compare_text]
                    
                    terms = [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]
                    if len(terms) >= 2:
                        from app.routers.timeline import compare_timeline
                        # Create a minimal request object for timeline endpoint
                        from starlette.requests import Request as StarletteRequest
                        from starlette.datastructures import Headers
                        dummy_scope = {
                            "type": "http",
                            "method": "GET",
                            "path": "/api/timeline/compare",
                            "headers": Headers(request.headers).raw,
                            "client": (request.client.host if request.client else "unknown", 0),
                        }
                        dummy_request = StarletteRequest(dummy_scope)
                        dummy_request._state = request.scope.get("state", {})
                        # Copy client info
                        if request.client:
                            dummy_request.client = request.client
                        
                        timeline_data = await compare_timeline(dummy_request, q=",".join(terms[:5]))  # Limit to 5 terms
                        timeline_json = timeline_data.body if hasattr(timeline_data, 'body') else None
                        if timeline_json:
                            import json
                            timeline_dict = json.loads(timeline_json.decode()) if isinstance(timeline_json, bytes) else timeline_json
                        else:
                            # Fallback: try to get from response
                            timeline_dict = {"ok": True, "terms": terms, "years": [], "datasets": []}
                        
                        if timeline_dict.get("ok") and timeline_dict.get("datasets"):
                            reply = f"📊 Comparing {len(terms)} entities: {', '.join(terms[:3])}"
                            if len(terms) > 3:
                                reply += f" and {len(terms) - 3} more"
                            return JSONResponse({
                                "ok": True,
                                "reply": reply,
                                "timeline": timeline_dict
                            })
                        else:
                            return _ok(f"Could not find timeline data for comparison of: {', '.join(terms)}")
                
                # 2. "When was X mentioned most?" queries
                if ("when was" in msg_lower or "when did" in msg_lower) and ("mentioned" in msg_lower or "appear" in msg_lower):
                    # Extract entity name
                    if "when was" in msg_lower:
                        term_text = msg_lower.split("when was")[1].split("mentioned")[0].split("appear")[0].strip()
                    elif "when did" in msg_lower:
                        term_text = msg_lower.split("when did")[1].split("mentioned")[0].split("appear")[0].strip()
                    else:
                        term_text = ""
                    
                    # Clean up term (remove common words)
                    term_text = term_text.replace("the", "").replace("a", "").replace("an", "").strip()
                    
                    if term_text and len(term_text) > 2:
                        from app.routers.timeline import timeline
                        from starlette.requests import Request as StarletteRequest
                        from starlette.datastructures import Headers
                        dummy_scope = {
                            "type": "http",
                            "method": "GET",
                            "path": "/api/timeline",
                            "headers": Headers(request.headers).raw,
                            "client": (request.client.host if request.client else "unknown", 0),
                        }
                        dummy_request = StarletteRequest(dummy_scope)
                        dummy_request._state = request.scope.get("state", {})
                        if request.client:
                            dummy_request.client = request.client
                        
                        timeline_data = await timeline(dummy_request, q=term_text)
                        timeline_json = timeline_data.body if hasattr(timeline_data, 'body') else None
                        if timeline_json:
                            import json
                            timeline_dict = json.loads(timeline_json.decode()) if isinstance(timeline_json, bytes) else timeline_json
                        else:
                            timeline_dict = {"ok": True, "term": term_text, "timeline": []}
                        
                        if timeline_dict.get("ok") and timeline_dict.get("timeline"):
                            timeline_list = timeline_dict.get("timeline", [])
                            if timeline_list:
                                best = max(timeline_list, key=lambda x: x.get("count", 0))
                                total = sum(p.get("count", 0) for p in timeline_list)
                                reply = f'📅 "{term_text}" was most mentioned in **{best.get("year")}** with **{best.get("count")}** article{"s" if best.get("count") != 1 else ""}.\n\nTotal mentions: {total} across {len(timeline_list)} year{"s" if len(timeline_list) != 1 else ""}.'
                                return JSONResponse({
                                    "ok": True,
                                    "reply": reply,
                                    "timeline": timeline_dict
                                })
                            else:
                                return _ok(f'No timeline data found for "{term_text}". Try tracking some articles first.')
                        else:
                            return _ok(f'No timeline data found for "{term_text}".')
                
                # 3. "Show articles about X from YYYY" queries
                if ("articles about" in msg_lower or "articles from" in msg_lower) and "from" in msg_lower:
                    # Extract term and year
                    parts = msg_lower.split("from")
                    if len(parts) >= 2:
                        term_part = parts[0].replace("articles about", "").replace("show", "").replace("find", "").strip()
                        year_part = parts[1].strip()[:4]  # Get first 4 digits
                        
                        # Try to extract year (look for 4-digit number)
                        import re
                        year_match = re.search(r'\b(19|20)\d{2}\b', year_part)
                        if not year_match:
                            year_match = re.search(r'\b(19|20)\d{2}\b', msg_lower)
                        year = year_match.group() if year_match else year_part[:4]
                        
                        if term_part and year and year.isdigit() and len(year) == 4:
                            from app.routers.timeline import timeline_hits
                            from starlette.requests import Request as StarletteRequest
                            from starlette.datastructures import Headers
                            dummy_scope = {
                                "type": "http",
                                "method": "GET",
                                "path": "/api/timeline/hits",
                                "headers": Headers(request.headers).raw,
                                "client": (request.client.host if request.client else "unknown", 0),
                            }
                            dummy_request = StarletteRequest(dummy_scope)
                            dummy_request._state = request.scope.get("state", {})
                            if request.client:
                                dummy_request.client = request.client
                            
                            hits_data = await timeline_hits(dummy_request, q=term_part, year=year)
                            hits_json = hits_data.body if hasattr(hits_data, 'body') else None
                            if hits_json:
                                import json
                                hits_dict = json.loads(hits_json.decode()) if isinstance(hits_json, bytes) else hits_json
                            else:
                                hits_dict = {"ok": True, "results": []}
                            
                            if hits_dict.get("ok") and hits_dict.get("results"):
                                results = hits_dict.get("results", [])
                                top_titles = [r.get("title", "Untitled") for r in results[:5]]
                                reply = f'📚 Found **{len(results)}** articles from **{year}** about "{term_part}":\n\n'
                                for idx, title in enumerate(top_titles, 1):
                                    reply += f'{idx}. {title}\n'
                                if len(results) > 5:
                                    reply += f'\n... and {len(results) - 5} more. Visit /notebook to see all articles with links.'
                                return JSONResponse({
                                    "ok": True,
                                    "reply": reply,
                                    "articles": results[:10]  # Include article data for potential rendering
                                })
                            else:
                                return _ok(f'No articles found for "{term_part}" from {year}.')
            except Exception as timeline_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Timeline query detection failed: {timeline_error}")
                # Fall through to analysis/LLM routing
            
            # Check for structured analysis queries (entity extraction, summarization)
            try:
                msg_lower = msg.lower()
                
                # 1. Entity extraction queries: "extract all people mentioned in..."
                if ("extract" in msg_lower or "find all" in msg_lower) and ("mentioned" in msg_lower or "people" in msg_lower or "entities" in msg_lower):
                    # Try to parse: "extract all people mentioned in 1915 Gallipoli articles"
                    # or "extract all people from 1915 Gallipoli articles"
                    
                    # Extract entity type
                    entity_type = None
                    entity_types_map = {
                        "people": ["PERSON"],
                        "person": ["PERSON"],
                        "persons": ["PERSON"],
                        "organizations": ["ORG"],
                        "orgs": ["ORG"],
                        "places": ["GPE", "LOC"],
                        "locations": ["GPE", "LOC"],
                        "events": ["EVENT"],
                        "facilities": ["FAC"],
                        "products": ["PRODUCT"]
                    }
                    for key, types in entity_types_map.items():
                        if key in msg_lower:
                            entity_type = types
                            break
                    
                    # Extract keywords and date
                    keywords = None
                    date_from = None
                    date_to = None
                    
                    # Look for year patterns
                    import re
                    year_match = re.search(r'\b(19|20)\d{2}\b', msg_lower)
                    if year_match:
                        year = year_match.group()
                        date_from = year
                        date_to = year
                    
                    # Look for date range
                    range_match = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', msg_lower)
                    if range_match:
                        date_from = range_match.group(1)
                        date_to = range_match.group(2)
                    
                    # Extract keywords (remove common words, extract topic)
                    # Try to find topic after "in" or "from"
                    if " in " in msg_lower:
                        parts = msg_lower.split(" in ")
                        if len(parts) > 1:
                            topic_part = parts[-1].split(" articles")[0].split(" from")[0].strip()
                            if topic_part and len(topic_part) > 2:
                                keywords = topic_part
                    elif " from " in msg_lower:
                        parts = msg_lower.split(" from ")
                        if len(parts) > 1:
                            topic_part = parts[0].split("mentioned")[-1].split("in")[-1].strip()
                            if topic_part and len(topic_part) > 2:
                                keywords = topic_part
                    
                    if entity_type or keywords or date_from:
                        from app.routers.analysis import extract_entities_from_articles, AnalysisRequest
                        from starlette.requests import Request as StarletteRequest
                        from starlette.datastructures import Headers
                        dummy_scope = {
                            "type": "http",
                            "method": "POST",
                            "path": "/api/analysis/extract-entities",
                            "headers": Headers(request.headers).raw,
                            "client": (request.client.host if request.client else "unknown", 0),
                        }
                        dummy_request = StarletteRequest(dummy_scope)
                        dummy_request._state = request.scope.get("state", {})
                        if request.client:
                            dummy_request.client = request.client
                        
                        analysis_req = AnalysisRequest(
                            keywords=keywords,
                            date_from=date_from,
                            date_to=date_to,
                            entity_types=entity_type,
                            max_articles=100
                        )
                        
                        result = await extract_entities_from_articles(dummy_request, analysis_req)
                        result_json = result.body if hasattr(result, 'body') else None
                        if result_json:
                            import json
                            result_dict = json.loads(result_json.decode()) if isinstance(result_json, bytes) else result_json
                        else:
                            result_dict = {"ok": True, "entities": []}
                        
                        if result_dict.get("ok") and result_dict.get("entities"):
                            entities_list = result_dict.get("entities", [])
                            entity_type_str = entity_type[0] if entity_type and len(entity_type) == 1 else "entities"
                            reply = f"📋 Extracted **{len(entities_list)}** {entity_type_str} from **{result_dict.get('articles_processed', 0)}** articles:\n\n"
                            for idx, ent in enumerate(entities_list[:10], 1):
                                reply += f"{idx}. **{ent.get('text')}** ({ent.get('label')}) - mentioned {ent.get('count')} time{'s' if ent.get('count') != 1 else ''}\n"
                            if len(entities_list) > 10:
                                reply += f"\n... and {len(entities_list) - 10} more. Visit /notebook to see all entities."
                            return JSONResponse({
                                "ok": True,
                                "reply": reply,
                                "entities": entities_list
                            })
                        else:
                            return _ok(f"No entities found matching the criteria.")
                
                # 2. Summarization queries: "summarise Australian coverage of WWII between 1939–1945"
                if ("summar" in msg_lower or "summarize" in msg_lower) and ("coverage" in msg_lower or "articles" in msg_lower or "about" in msg_lower):
                    # Extract keywords and date range
                    keywords = None
                    date_from = None
                    date_to = None
                    
                    # Look for date range
                    import re
                    range_match = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', msg_lower)
                    if range_match:
                        date_from = range_match.group(1)
                        date_to = range_match.group(2)
                    else:
                        # Look for single year
                        year_match = re.search(r'\b(19|20)\d{2}\b', msg_lower)
                        if year_match:
                            year = year_match.group()
                            date_from = year
                            date_to = year
                    
                    # Extract topic/keywords
                    # Pattern: "summarise [topic] coverage of [subject]"
                    if " coverage of " in msg_lower:
                        parts = msg_lower.split(" coverage of ")
                        if len(parts) > 1:
                            topic = parts[1].split(" between")[0].split(" from")[0].split(" in")[0].strip()
                            if topic and len(topic) > 2:
                                keywords = topic
                    elif " about " in msg_lower:
                        parts = msg_lower.split(" about ")
                        if len(parts) > 1:
                            topic = parts[1].split(" between")[0].split(" from")[0].split(" in")[0].strip()
                            if topic and len(topic) > 2:
                                keywords = topic
                    
                    if keywords or date_from:
                        from app.routers.analysis import summarize_articles, AnalysisRequest
                        from starlette.requests import Request as StarletteRequest
                        from starlette.datastructures import Headers
                        dummy_scope = {
                            "type": "http",
                            "method": "POST",
                            "path": "/api/analysis/summarize",
                            "headers": Headers(request.headers).raw,
                            "client": (request.client.host if request.client else "unknown", 0),
                        }
                        dummy_request = StarletteRequest(dummy_scope)
                        dummy_request._state = request.scope.get("state", {})
                        if request.client:
                            dummy_request.client = request.client
                        
                        analysis_req = AnalysisRequest(
                            keywords=keywords,
                            date_from=date_from,
                            date_to=date_to,
                            max_articles=100,
                            use_llm=True
                        )
                        
                        result = await summarize_articles(dummy_request, analysis_req)
                        result_json = result.body if hasattr(result, 'body') else None
                        if result_json:
                            import json
                            result_dict = json.loads(result_json.decode()) if isinstance(result_json, bytes) else result_json
                        else:
                            result_dict = {"ok": True, "summary": ""}
                        
                        if result_dict.get("ok") and result_dict.get("summary"):
                            summary = result_dict.get("summary", "")
                            bullets = result_dict.get("bullets", [])
                            article_count = result_dict.get("articles_processed", 0)
                            reply = f"📝 Summary of **{article_count}** articles"
                            if keywords:
                                reply += f" about '{keywords}'"
                            if date_from and date_to:
                                reply += f" from {date_from}–{date_to}"
                            reply += ":\n\n"
                            if bullets:
                                reply += "\n".join(f"• {b}" for b in bullets[:10])
                            else:
                                reply += summary[:1000]
                            if len(summary) > 1000:
                                reply += "..."
                            return JSONResponse({
                                "ok": True,
                                "reply": reply,
                                "summary": summary,
                                "bullets": bullets
                            })
                        else:
                            return _ok(f"No articles found to summarize matching the criteria.")
            except Exception as analysis_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Analysis query detection failed: {analysis_error}")
                # Fall through to LLM routing
            
            # Non-slash command - handle with LLM routing
            try:
                # Get research context from SQLite (persistent, pinned-first)
                from ..context_store import pack_for_prompt
                packed = pack_for_prompt(session_key, max_chars=3500)
                context_text = packed["text"]
                
                # Route message with context
                routed = chat_llm.route_message(msg, context=context_text)
                if routed and "command" in routed:
                    # LLM routed to a command - execute it recursively
                    return await chat(ChatIn(message=routed["command"]), request)
                elif routed and "say" in routed:
                    # LLM provided a conversational response
                    return _ok(routed["say"])
            except Exception as llm_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.exception(f"LLM routing error: {llm_error}")
                # Fall through to default response with helpful error message
                error_msg = str(llm_error)
                if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                    return _ok("⚠️ OpenAI API rate limit reached. Please try again in a moment, or use slash commands directly:\n/search <query> - Search archives\n/read <id> - Read article\nType /help for all commands.")
                elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                    return _ok("⚠️ OpenAI API configuration issue. You can still use commands:\n/search <query> - Search archives\n/read <id> - Read article\nType /help for all commands.")
                # Fall through to default
            
            # LLM not enabled, failed, or no routing - provide helpful response
            from ..context_store import pack_for_prompt
            packed = pack_for_prompt(session_key, max_chars=500)
            count = packed.get("count", 0)
            
            # Try to provide a more helpful response based on the message
            msg_lower = msg.lower()
            if any(word in msg_lower for word in ["search", "find", "look for", "discover"]):
                # Extract search terms
                search_terms = msg.replace("search for", "").replace("find", "").replace("look for", "").strip()
                if search_terms and len(search_terms) > 2:
                    return _ok(f"I can help you search! Since AI chat isn't available, try:\n\n/search {search_terms}\n\nOr use the search page: /search?q={search_terms}\n\nType /help for all commands.")
            
            if count > 0:
                return _ok(f"I can help you search Trove archives! I have {count} articles in context from your research.\n\n**Available commands:**\n/search <query> - Search archives\n/suggest-searches <topic> - Get suggestions\n/read <id> - Read article\n/cite <id> - Pin and cite article\n/context - View your research context\n\nType /help for all commands.")
            else:
                return _ok("I can help you search Trove archives!\n\n**Quick Start:**\n/search <query> - Search archives (e.g., /search gold discoveries)\n/suggest-searches <topic> - Get search suggestions\n/read <id> - Read article by ID\n\n**Natural language:** Try asking 'search for [topic]' or 'find articles about [topic]'\n\nType /help for all commands.")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Chat error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# Mobile app API endpoints (compatible with apps/api/app/main.py)
@router.post("/api/trove/search")
async def api_trove_search_mobile(
    body: dict = Body(...),
):
    """Mobile-compatible Trove search endpoint with sensitive research mode."""
    from .lexicon import expand_query
    from app.config import get_settings
    from app.trove_client import TroveClient
    from app.services import TroveSearchService
    
    # Extract parameters from body
    q = body.get("q", "")
    n = body.get("n", 20)
    sensitive_mode = body.get("sensitive_mode", False)
    date_from = body.get("date_from")
    date_to = body.get("date_to")
    state = body.get("state")
    
    try:
        settings = get_settings()
        if not settings.trove_api_key:
            return JSONResponse({"ok": False, "error": "TROVE_API_KEY not configured"}, status_code=500)
        
        client = TroveClient(
            api_key=settings.trove_api_key,
            base_url=settings.trove_base_url,
            timeout=settings.trove_timeout,
        )
        service = TroveSearchService(client)
        
        # Expand query if sensitive mode is enabled
        expanded_query = expand_query(q, sensitive_mode)
        
        # Search Trove
        records, total = await service.search(
            q=expanded_query,
            category="newspaper",
            n=min(n, 100),
            s=0,
        )
        
        # Convert to mobile app format
        items = []
        for record in records:
            items.append({
                "id": str(record.id),
                "title": record.title,
                "date": record.issued or "",
                "page": getattr(record, "page", ""),
                "snippet": record.snippet or "",
                "troveUrl": record.trove_url or "",
            })
        
        return JSONResponse({
            "ok": True,
            "query_used": expanded_query,
            "items": items,
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Mobile search error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/trove/article")
async def api_trove_article_mobile(
    id_or_url: str = Query(...),
    pdf: bool = Query(False),
):
    """Mobile-compatible article fetch endpoint."""
    from .article_io import extract_article_id_from_url, fetch_item_text
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    try:
        # Extract article ID
        article_id = extract_article_id_from_url(id_or_url) or id_or_url
        
        # Fetch article
        data = await fetch_item_text(article_id)
        
        if not data.get("ok"):
            return JSONResponse({"ok": False, "error": data.get("error", "Failed to fetch article")}, status_code=500)
        
        article = {
            "id": data.get("id"),
            "heading": data.get("title") or data.get("heading"),
            "title": data.get("title"),
            "date": data.get("date") or data.get("issued", ""),
            "page": data.get("page", ""),
            "troveUrl": data.get("url") or data.get("trove_url", ""),
            "text": data.get("text") or data.get("snippet", ""),
        }
        
        if pdf:
            # Generate PDF inline
            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            width, height = A4
            y = height - 50
            title = (article.get("heading") or article.get("title") or f"Trove article {article_id}")[:120]
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(width/2, y, title)
            y -= 20
            meta = f"{article.get('date','')}  |  Page {article.get('page','')}  |  {article.get('troveUrl','')}"
            c.setFont("Helvetica", 9)
            c.drawCentredString(width/2, y, meta)
            y -= 20
            c.setFont("Times-Roman", 11)
            for line in article.get("text","").splitlines():
                for chunk in [line[i:i+100] for i in range(0,len(line),100)]:
                    if y < 50:
                        c.showPage()
                        y = height - 50
                        c.setFont("Times-Roman", 11)
                    c.drawString(50, y, chunk)
                    y -= 14
            c.showPage()
            c.save()
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="trove_{article_id}.pdf"'}
            )
        
        return JSONResponse({"ok": True, "article": article})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Article fetch error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/ping")
async def api_ping():
    """Health check endpoint for mobile app."""
    return {"ok": True}


def init_archive_detective(app: FastAPI) -> None:
    """Initialize Archive Detective routes on the FastAPI app."""
    app.include_router(router)

