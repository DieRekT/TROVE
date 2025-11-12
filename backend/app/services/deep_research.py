from __future__ import annotations
import re
import os
import logging
import json
from typing import List, Dict, AsyncGenerator, Any
from .trove_client import TroveClient
from .llm import synthesize_research
from .ranking import bm25_to_score, title_overlap, date_proximity, blend
from .geo import nsw_bonus_for_text, infer_state_from_query
from .quotes import best_sentences

logger = logging.getLogger(__name__)
from ..models.deep_research import (
    DeepResearchRequest,
    DeepResearchResponse,
    SourceItem,
    Finding,
    TimelineItem,
)
from ..utils.cache import TTLCache
from .web_search import search_web


_cache = TTLCache(ttl_sec=300)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

TOPIC_MINE = re.compile(r'\b(mine|mining|mineral|lease|ilmenite|rutile|zircon|sand|sands|beach|placer|dredg)\b', re.I)
TOPIC_GEO = re.compile(r'\b(Iluka|Yamba|Clarence River|Angourie|Woody Head|Shark Bay)\b', re.I)

def _is_on_topic(title: str, snippet: str, text: str) -> bool:
    blob = " ".join([title or "", snippet or "", text or ""])
    return bool(TOPIC_MINE.search(blob)) and bool(TOPIC_GEO.search(blob))



def _short(s: str, n: int = 220) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def _terms(q: str) -> List[str]:
    return [w for w in re.split(r"[^a-z0-9]+", q.lower()) if w and len(w) > 2]


def _best_sentences(text: str, terms: List[str], max_out: int = 2) -> List[str]:
    """Use improved quote extraction service."""
    return best_sentences(text, terms, k=max_out)


def _bm25lite(text: str, terms: List[str]) -> float:
    t = (text or "").lower()
    dl = max(1, len(t.split()))
    score = 0.0
    for term in set(terms):
        tf = t.count(term)
        if tf:
            score += (tf / (tf + 1.5)) * (1.2 * (1 + 0.75 * (1000 / dl)))
    return score


async def run_deep_research(req: DeepResearchRequest) -> DeepResearchResponse:
    # Stage A: Cache check (key matches spec)
    key = f"{req.query}|{req.years_from}|{req.years_to}|{req.max_sources}|{req.depth}"
    cached = _cache.get(key)
    if cached:
        return cached

    terms = _terms(req.query)
    sources: List[SourceItem] = []
    raw_trove_count = 0
    dropped = 0
    
    # Calculate how many pages to fetch based on depth
    # Standard: 2 pages (40 results), Deep: 5 pages (100 results), Brief: 1 page
    pages_to_fetch = {
        "brief": 1,
        "standard": 2,
        "deep": 5
    }.get(req.depth or "standard", 2)
    
    # Increase max_sources for deep searches
    effective_max = req.max_sources
    if req.depth == "deep":
        effective_max = max(req.max_sources, 50)  # At least 50 for deep
    elif req.depth == "standard":
        effective_max = max(req.max_sources, 30)  # At least 30 for standard
    
    # Stage B: Evidence retrieval (Trove)
    try:
        trove = TroveClient()
        # Infer state from query for better filtering
        inferred_state = infer_state_from_query(req.query)
        
        # Fetch multiple pages for deeper search
        raw = []
        page_size = 20  # Trove API max per page
        for page in range(pages_to_fetch):
            offset = page * page_size
            try:
                payload = await trove.search(
                    q=req.query,
                    n=page_size,
                    offset=offset,
                    year_from=req.years_from if page == 0 else None,  # Only filter on first page
                    year_to=req.years_to if page == 0 else None,
                    reclevel="brief",
                    include="",
                    state=inferred_state
                )
                page_results = TroveClient.extract_hits(payload)
                raw.extend(page_results)
                if len(page_results) < page_size:
                    break  # No more results
            except Exception as e:
                logger.warning(f"Failed to fetch page {page + 1}: {e}")
                break
        
        raw_trove_count = len(raw)
        
        # If no results with year filter, try without year filter (year filter might be too restrictive)
        if raw_trove_count == 0 and (req.years_from or req.years_to):
            logger.info(f"No results with year filter {req.years_from}-{req.years_to}, trying without year filter")
            raw = []
            for page in range(pages_to_fetch):
                offset = page * page_size
                try:
                    payload = await trove.search(
                        q=req.query,
                        n=page_size,
                        offset=offset,
                        year_from=None,
                        year_to=None,
                        reclevel="brief",
                        include="",
                        state=inferred_state
                    )
                    page_results = TroveClient.extract_hits(payload)
                    raw.extend(page_results)
                    if len(page_results) < page_size:
                        break
                except Exception as e:
                    logger.warning(f"Failed to fetch page {page + 1}: {e}")
                    break
            raw_trove_count = len(raw)

        for rec in raw:
            sid = str(
                rec.get("id")
                or rec.get("workId")
                or rec.get("articleId")
                or rec.get("recordId")
                or "UNKNOWN"
            )
            title = rec.get("heading") or rec.get("title") or "Untitled"
            url = TroveClient.article_url(rec)
            year = TroveClient.year_from_any(rec)
            # With reclevel="brief", articleText may not be available, use snippet first
            full = (rec.get("snippet") or "") + " " + (rec.get("articleText") or "")
            snips = _best_sentences(full, terms, max_out=2)
            
            # Calculate improved relevance score
            txt = " ".join(
                [
                    str(rec.get("heading", "")),
                    str(rec.get("snippet", "")),
                    str(rec.get("articleText", "")),
                ]
            )
            # Use BM25-like scoring as baseline, then blend with boosts
            bm25_lite = _bm25lite(txt, terms)
            bm25_norm = bm25_to_score(bm25_lite) if bm25_lite > 0 else 0.5
            tb = title_overlap(str(title), terms)
            dp = date_proximity(year, req.years_from, req.years_to)
            nswb = nsw_bonus_for_text(txt)
            rel = blend(bm25_norm, tb, dp, nswb)
            
            # Apply topic guard - only keep mining-related sources with location match
            on_topic = _is_on_topic(title, rec.get('snippet') or '', full)
            if not on_topic:
                dropped += 1
                continue
            
            sources.append(
                SourceItem(
                    id=f"TROVE:{sid}",
                    title=str(title),
                    type=str(rec.get("type", "article")),
                    year=year,
                    url=url,
                    snippets=snips,
                    relevance=rel,
                )
            )
    except Exception as e:
        logger.warning(f"Trove search failed: {e}, continuing with web search only")
        raw = []
    
    # Optional: Search web (if enabled)
    web_enabled = os.getenv("WEB_SEARCH_ENABLED", "0") == "1"
    raw_web_count = 0
    if web_enabled:
        try:
            # Determine how many web sources to fetch
            web_max = max(6, req.max_sources // 2)
            
            web_results = await search_web(
                query=req.query,
                max_results=web_max,
                timeout=22.0,
                prefer_recent=req.prefer_recent,
                fetch_content=True,
            )
            raw_web_count = len(web_results)
            
            # Convert web results to SourceItem
            for web_result in web_results:
                # Extract year from date if available
                year = None
                if web_result.date:
                    try:
                        year_match = re.search(r"\d{4}", web_result.date)
                        if year_match:
                            year = int(year_match.group())
                    except Exception:
                        pass
                
                # Use quotes if available, otherwise use snippet
                snippets = web_result.quotes if web_result.quotes else [web_result.snippet[:240]]
                
                sources.append(
                    SourceItem(
                        id=f"WEB:{web_result.url}",
                        title=web_result.title,
                        type="web",
                        year=year,
                        url=web_result.url,
                        snippets=snippets,
                        relevance=web_result.relevance_score,
                    )
                )
        except Exception as e:
            logger.warning(f"Web search failed: {e}, continuing with Trove only")

    # Stage C: Ranking (BM25-lite + hygiene)
    # Normalize relevance scores to 0..1 range (higher is better)
    if sources:
        rels = [s.relevance for s in sources]
        rmin, rmax = min(rels), max(rels)
        span = max(1e-9, (rmax - rmin))
        for s in sources:
            s.relevance = max(0.0, min(1.0, (s.relevance - rmin) / span))
    
    # Apply state filtering if requested
    if req.region:
        # Defensive filter: check title/metadata for state hints
        filtered = []
        for s in sources:
            # Check if source metadata indicates a different state
            # This is a best-effort filter based on title patterns
            title_lower = s.title.lower()
            if req.region.lower() in ["new south wales", "nsw", "n.s.w."]:
                # Filter out obvious WA sources
                if any(hint in title_lower for hint in ["(w.a.)", "western australia", "perth", "fremantle"]):
                    continue
            elif req.region.lower() in ["western australia", "wa", "w.a."]:
                # Filter out obvious NSW sources
                if any(hint in title_lower for hint in ["(n.s.w.)", "new south wales", "sydney", "clarence"]):
                    continue
            filtered.append(s)
        sources = filtered
    
    # Use effective_max if defined, otherwise req.max_sources
    try:
        max_sources_limit = effective_max
    except NameError:
        max_sources_limit = req.max_sources
    sources_sorted = sorted(sources, key=lambda s: s.relevance, reverse=True)[:max_sources_limit]

    # Stage D: LLM synthesis (OpenAI Responses + Structured Outputs)
    try:
        # Prepare source dicts for LLM
        source_dicts = [
            {
                "id": s.id,
                "title": s.title,
                "year": s.year,
                "url": s.url,
                "snippets": s.snippets,
            }
            for s in sources_sorted[:8]  # Top ~8 for synthesis
        ]
        
        llm_result = await synthesize_research(
            query=req.query,
            sources=source_dicts,
            depth=req.depth,
        )
        
        # Convert LLM results to model objects
        findings = [
            Finding(
                title=f.get("title", "Untitled"),
                insight=f.get("insight", ""),
                evidence=f.get("evidence", []),
                citations=f.get("citations", []),
                confidence=f.get("confidence", 0.65),
            )
            for f in llm_result.get("key_findings", [])
        ]
        
        timeline = [
            TimelineItem(
                date=t.get("date"),
                event=t.get("event", ""),
                citations=t.get("citations", []),
            )
            for t in llm_result.get("timeline", [])
        ]
        
        executive_summary = llm_result.get("executive_summary", "")
        
    except Exception as e:
        logger.error(f"LLM synthesis failed: {e}, using fallback")
        # Fallback: minimal deterministic report
        findings = []
        timeline = []
        for s in sources_sorted[:3]:
            findings.append(
                Finding(
                    title=s.title[:80],
                    insight=f"Source {s.id} provides relevant information about '{req.query}'.",
                    evidence=s.snippets[:2],
                    citations=[s.id],
                    confidence=0.5,
                )
            )
            if s.year:
                timeline.append(
                    TimelineItem(
                        date=f"{s.year}-01-01",
                        event=s.title[:120],
                        citations=[s.id],
                    )
                )
        executive_summary = f"This report synthesizes {len(sources_sorted)} sources related to '{req.query}'. Evidence may be limited; verify claims with primary sources."

    # Stage E: Assemble final response
    entities = {"people": [], "organisations": [], "places": [], "topics": []}
    
    resp = DeepResearchResponse(
        query=req.query,
        executive_summary=executive_summary,
        key_findings=findings,
        timeline=sorted(timeline, key=lambda t: (t.date or "")),
        entities=entities,
        sources=sources_sorted,
        methodology=[
            "trove.v3 search",
            "normalisation",
            "BM25-lite ranking",
            "sentence quote extraction",
            "LLM synthesis (OpenAI)",
        ],
        limitations=[
            "No OCR repair or cross-archive corroboration yet",
            "Evidence limited to available sources; verify claims independently",
        ],
        next_questions=[
            "Which claims need non-newspaper corroboration?",
            "What maps/gazettes/registers confirm dates and actors?",
        ],
        stats={
            "retrieved": raw_trove_count + raw_web_count,
            "dropped_offtopic": dropped,
            "used": len(sources_sorted),
        },
    )
    _cache.set(key, resp)
    return resp


async def run_deep_research_stream(
    req: DeepResearchRequest,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Streaming version that yields progress updates."""
    import asyncio
    
    # Stage A: Cache check
    key = f"{req.query}|{req.years_from}|{req.years_to}|{req.max_sources}|{req.depth}"
    cached = _cache.get(key)
    if cached:
        yield {"type": "cached", "data": cached.dict()}
        return
    
    yield {"type": "progress", "stage": "searching", "message": "🔍 Searching Trove archives...", "progress": 10}
    
    terms = _terms(req.query)
    sources: List[SourceItem] = []
    raw_trove_count = 0
    
    # Stage B: Evidence retrieval (Trove)
    try:
        trove = TroveClient()
        payload = await trove.search(
            q=req.query,
            n=req.max_sources,
            year_from=req.years_from,
            year_to=req.years_to,
            reclevel="brief",  # Changed from "full" to avoid 400 errors with Trove API v3
            include="",  # Removed articleText,links to avoid 400 errors
        )
        raw = TroveClient.extract_hits(payload)
        raw_trove_count = len(raw)
        dropped = 0
        
        yield {"type": "progress", "stage": "found", "message": f"✅ Found {raw_trove_count} sources", "progress": 30, "count": raw_trove_count}

        for rec in raw:
            sid = str(
                rec.get("id")
                or rec.get("workId")
                or rec.get("articleId")
                or rec.get("recordId")
                or "UNKNOWN"
            )
            title = rec.get("heading") or rec.get("title") or "Untitled"
            url = TroveClient.article_url(rec)
            year = TroveClient.year_from_any(rec)
            # With reclevel="brief", articleText may not be available, use snippet first
            full = (rec.get("snippet") or "") + " " + (rec.get("articleText") or "")
            snips = _best_sentences(full, terms, max_out=2)
            txt = " ".join(
                [
                    str(rec.get("heading", "")),
                    str(rec.get("snippet", "")),
                    str(rec.get("articleText", "")),
                ]
            )
            rel = _bm25lite(txt, terms)
            sources.append(
                SourceItem(
                    id=f"TROVE:{sid}",
                    title=str(title),
                    type=str(rec.get("type", "article")),
                    year=year,
                    url=url,
                    snippets=snips,
                    relevance=rel,
                )
            )
    except Exception as e:
        logger.warning(f"Trove search failed: {e}, continuing with web search only")
        raw = []
    
    # Optional: Search web (if enabled)
    web_enabled = os.getenv("WEB_SEARCH_ENABLED", "0") == "1"
    raw_web_count = 0
    if web_enabled:
        yield {"type": "progress", "stage": "web_search", "message": "🌐 Searching web sources...", "progress": 40}
        try:
            web_max = max(6, req.max_sources // 2)
            
            web_results = await search_web(
                query=req.query,
                max_results=web_max,
                timeout=22.0,
                prefer_recent=req.prefer_recent,
                fetch_content=True,
            )
            raw_web_count = len(web_results)
            
            for web_result in web_results:
                year = None
                if web_result.date:
                    try:
                        year_match = re.search(r"\d{4}", web_result.date)
                        if year_match:
                            year = int(year_match.group())
                    except Exception:
                        pass
                
                snippets = web_result.quotes if web_result.quotes else [web_result.snippet[:240]]
                
                sources.append(
                    SourceItem(
                        id=f"WEB:{web_result.url}",
                        title=web_result.title,
                        type="web",
                        year=year,
                        url=web_result.url,
                        snippets=snippets,
                        relevance=web_result.relevance_score,
                    )
                )
        except Exception as e:
            logger.warning(f"Web search failed: {e}, continuing with Trove only")

    # Stage C: Ranking
    yield {"type": "progress", "stage": "ranking", "message": "📊 Ranking sources by relevance...", "progress": 50}
    
    # Normalize relevance scores to 0..1 range (higher is better)
    if sources:
        rels = [s.relevance for s in sources]
        rmin, rmax = min(rels), max(rels)
        span = max(1e-9, (rmax - rmin))
        for s in sources:
            s.relevance = max(0.0, min(1.0, (s.relevance - rmin) / span))
    
    # Apply state filtering if requested
    if req.region:
        filtered = []
        for s in sources:
            title_lower = s.title.lower()
            if req.region.lower() in ["new south wales", "nsw", "n.s.w."]:
                if any(hint in title_lower for hint in ["(w.a.)", "western australia", "perth", "fremantle"]):
                    continue
            elif req.region.lower() in ["western australia", "wa", "w.a."]:
                if any(hint in title_lower for hint in ["(n.s.w.)", "new south wales", "sydney", "clarence"]):
                    continue
            filtered.append(s)
        sources = filtered
    
    # Use effective_max if defined, otherwise req.max_sources
    try:
        max_sources_limit = effective_max
    except NameError:
        max_sources_limit = req.max_sources
    sources_sorted = sorted(sources, key=lambda s: s.relevance, reverse=True)[:max_sources_limit]

    # Stage D: LLM synthesis
    yield {"type": "progress", "stage": "analyzing", "message": "🧠 Analyzing content...", "progress": 60}
    
    try:
        source_dicts = [
            {
                "id": s.id,
                "title": s.title,
                "year": s.year,
                "url": s.url,
                "snippets": s.snippets,
            }
            for s in sources_sorted[:8]
        ]
        
        yield {"type": "progress", "stage": "synthesizing", "message": "✨ Synthesizing report with AI...", "progress": 70}
        
        llm_result = await synthesize_research(
            query=req.query,
            sources=source_dicts,
            depth=req.depth,
        )
        
        findings = [
            Finding(
                title=f.get("title", "Untitled"),
                insight=f.get("insight", ""),
                evidence=f.get("evidence", []),
                citations=f.get("citations", []),
                confidence=f.get("confidence", 0.65),
            )
            for f in llm_result.get("key_findings", [])
        ]
        
        timeline = [
            TimelineItem(
                date=t.get("date"),
                event=t.get("event", ""),
                citations=t.get("citations", []),
            )
            for t in llm_result.get("timeline", [])
        ]
        
        executive_summary = llm_result.get("executive_summary", "")
        
    except Exception as e:
        logger.error(f"LLM synthesis failed: {e}, using fallback")
        findings = []
        timeline = []
        for s in sources_sorted[:3]:
            findings.append(
                Finding(
                    title=s.title[:80],
                    insight=f"Source {s.id} provides relevant information about '{req.query}'.",
                    evidence=s.snippets[:2],
                    citations=[s.id],
                    confidence=0.5,
                )
            )
            if s.year:
                timeline.append(
                    TimelineItem(
                        date=f"{s.year}-01-01",
                        event=s.title[:120],
                        citations=[s.id],
                    )
                )
        executive_summary = f"This report synthesizes {len(sources_sorted)} sources related to '{req.query}'. Evidence may be limited; verify claims with primary sources."

    # Stage E: Assemble final response
    yield {"type": "progress", "stage": "finalizing", "message": "📝 Finalizing report...", "progress": 90}
    
    entities = {"people": [], "organisations": [], "places": [], "topics": []}
    
    resp = DeepResearchResponse(
        query=req.query,
        executive_summary=executive_summary,
        key_findings=findings,
        timeline=sorted(timeline, key=lambda t: (t.date or "")),
        entities=entities,
        sources=sources_sorted,
        methodology=[
            "trove.v3 search",
            "normalisation",
            "BM25-lite ranking",
            "sentence quote extraction",
            "LLM synthesis (OpenAI)",
        ],
        limitations=[
            "No OCR repair or cross-archive corroboration yet",
            "Evidence limited to available sources; verify claims independently",
        ],
        next_questions=[
            "Which claims need non-newspaper corroboration?",
            "What maps/gazettes/registers confirm dates and actors?",
        ],
        stats={
            "retrieved": raw_trove_count + raw_web_count,
            "dropped_offtopic": dropped,
            "used": len(sources_sorted),
        },
    )
    _cache.set(key, resp)
    
    yield {"type": "progress", "stage": "complete", "message": "🎉 Research complete!", "progress": 100}
    yield {"type": "result", "data": resp.dict()}

