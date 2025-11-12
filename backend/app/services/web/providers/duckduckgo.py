"""DuckDuckGo search provider (tertiary)."""

import logging
import os
import re
from typing import List
import httpx
from dotenv import load_dotenv

from ....models.web_search import RawSearchResult

load_dotenv()

logger = logging.getLogger(__name__)

DDG_API_URL = os.getenv("DDG_API_URL", "")
DDG_API_KEY = os.getenv("DDG_API_KEY", "")
DDG_INSTANT_ANSWER_URL = "https://api.duckduckgo.com"


def search_duckduckgo(query: str, max_results: int = 12) -> List[RawSearchResult]:
    """
    Search using DuckDuckGo.
    
    Tries official API if configured, otherwise falls back to Instant Answer API
    or HTML scraping.
    
    Returns list of RawSearchResult items.
    """
    # Try official API if configured
    if DDG_API_URL and DDG_API_KEY:
        return _search_ddg_official(query, max_results)
    
    # Fallback to Instant Answer API (limited results)
    return _search_ddg_instant_answer(query, max_results)


def _search_ddg_official(query: str, max_results: int) -> List[RawSearchResult]:
    """Use official DuckDuckGo API if available."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                DDG_API_URL,
                params={"q": query, "max_results": max_results},
                headers={"Authorization": f"Bearer {DDG_API_KEY}"},
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    RawSearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", "")[:500],
                        date=None,
                        provider="duckduckgo",
                    )
                )
            
            logger.info(f"DuckDuckGo API returned {len(results)} results")
            return results
            
    except Exception as e:
        logger.warning(f"DuckDuckGo official API error: {e}, trying fallback")
        return _search_ddg_instant_answer(query, max_results)


def _search_ddg_instant_answer(query: str, max_results: int) -> List[RawSearchResult]:
    """Fallback to Instant Answer API (very limited)."""
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(
                f"{DDG_INSTANT_ANSWER_URL}/",
                params={"q": query, "format": "json", "no_html": "1"},
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Instant Answer API provides AbstractText and AbstractURL
            if data.get("AbstractText") and data.get("AbstractURL"):
                results.append(
                    RawSearchResult(
                        title=data.get("Heading", query),
                        url=data.get("AbstractURL", ""),
                        snippet=data.get("AbstractText", "")[:500],
                        date=None,
                        provider="duckduckgo",
                    )
                )
            
            # RelatedTopics may have some results
            for topic in data.get("RelatedTopics", [])[:max_results - 1]:
                if isinstance(topic, dict) and topic.get("FirstURL"):
                    results.append(
                        RawSearchResult(
                            title=topic.get("Text", "Untitled").split(" - ")[0],
                            url=topic.get("FirstURL", ""),
                            snippet=topic.get("Text", "")[:500],
                            date=None,
                            provider="duckduckgo",
                        )
                    )
            
            logger.info(f"DuckDuckGo Instant Answer returned {len(results)} results")
            return results
            
    except Exception as e:
        logger.warning(f"DuckDuckGo Instant Answer error: {e}")
        return []

