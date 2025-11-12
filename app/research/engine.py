"""OpenAI Responses API engine with Web tool integration."""

import json
import logging
import os
import asyncio
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from app.research.schemas import Citation, Evidence, Findings

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o1-mini")
OPENAI_ENABLE_WEB = os.getenv("OPENAI_ENABLE_WEB", "1") == "1"
MAX_WEB_RESULTS = int(os.getenv("OPENAI_WEB_SEARCH_MAX_RESULTS", "12"))
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "1") == "1"


def call_openai_web(query: str, context_hints: Optional[str] = None) -> List[Evidence]:
    """
    Call web search aggregator for search and page reading.

    Returns Evidence items from web search and page content.
    """
    if not WEB_SEARCH_ENABLED:
        logger.info("Web search disabled, skipping")
        return []

    try:
        # Use the backend web search aggregator
        # Note: This is a sync function, so we need to run async in a new event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Import here to avoid circular imports
        from backend.app.services.web_search import search_web
        
        # Run async search
        web_results = loop.run_until_complete(
            search_web(
                query=query,
                max_results=MAX_WEB_RESULTS,
                timeout=22.0,
                prefer_recent=False,
                fetch_content=True,
            )
        )
        
        # Convert WebSearchResult to Evidence
        evidence_list: List[Evidence] = []
        for result in web_results:
            # Use quotes if available, otherwise snippet
            quotes = result.quotes if result.quotes else [result.snippet[:240]]
            
            evidence_list.append(
                Evidence(
                    title=result.title,
                    url=result.url,
                    source="web",
                    published_at=result.date,
                    snippet=result.snippet,
                    quotes=quotes,
                    score=result.relevance_score,
                    rationale=f"Relevant web source from {result.provider} (domain: {result.domain})",
                )
            )
        
        logger.info(f"Web search returned {len(evidence_list)} evidence items")
        return evidence_list

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return []


def _fallback_web_search(query: str) -> List[Evidence]:
    """Fallback web search using simple HTTP requests."""
    # This is a placeholder - in production you'd use a proper search API
    logger.warning("Using fallback web search (limited functionality)")
    return []


def synthesize_findings(evidence_list: List[Evidence], question: str) -> Findings:
    """
    Synthesize evidence into structured Findings using OpenAI.

    Returns Findings with overview, key points, limitations, next questions, and citations.
    """
    if not OPENAI_API_KEY:
        # Fallback synthesis without AI
        return _fallback_synthesis(evidence_list, question)

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Prepare evidence summary
    evidence_text = "\n\n".join(
        [
            f"Title: {e.title}\nURL: {e.url}\nSource: {e.source}\nSnippet: {e.snippet[:300]}"
            for e in evidence_list[:20]  # Limit to top 20
        ]
    )

    prompt = f"""Based on the following evidence, synthesize findings for this research question:

Question: {question}

Evidence:
{evidence_text}

Please provide:
1. A 5-8 sentence overview
2. 6-10 key points (each with source tags like [Source: title])
3. Limitations of this research
4. Suggested next questions
5. A complete citation list (title, URL, source)

Format as JSON with keys: overview, key_points (array), limitations (array), next_questions (array), citations (array of {{title, url, source}})."""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        citations = [
            Citation(title=c.get("title", ""), url=c.get("url", ""), source=c.get("source", "web"))
            for c in data.get("citations", [])
        ]

        return Findings(
            overview=data.get("overview", ""),
            key_points=data.get("key_points", []),
            limitations=data.get("limitations", []),
            next_questions=data.get("next_questions", []),
            citations=citations,
        )

    except Exception as e:
        logger.error(f"Error synthesizing findings: {e}")
        return _fallback_synthesis(evidence_list, question)


def _fallback_synthesis(evidence_list: List[Evidence], question: str) -> Findings:
    """Fallback synthesis without AI."""
    citations = [
        Citation(title=e.title, url=e.url, source=e.source) for e in evidence_list[:20]
    ]

    key_points = [f"{e.title} ({e.source})" for e in evidence_list[:10]]

    return Findings(
        overview=f"Research on '{question}' found {len(evidence_list)} evidence items from web and Trove sources.",
        key_points=key_points,
        limitations=["AI synthesis not available - using basic summary"],
        next_questions=[f"Further investigation into specific aspects of: {question}"],
        citations=citations,
    )

