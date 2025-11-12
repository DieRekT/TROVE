"""Tavily search provider (primary)."""

import logging
import os
from typing import List, Optional
import httpx
from dotenv import load_dotenv

from ....models.web_search import RawSearchResult

load_dotenv()

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = "https://api.tavily.com"


def search_tavily(query: str, max_results: int = 12) -> List[RawSearchResult]:
    """
    Search using Tavily API.
    
    Returns list of RawSearchResult items.
    """
    if not TAVILY_API_KEY:
        logger.debug("TAVILY_API_KEY not set, skipping Tavily search")
        return []
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{TAVILY_BASE_URL}/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    RawSearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:500],  # Limit snippet length
                        date=None,  # Tavily doesn't provide dates
                        provider="tavily",
                    )
                )
            
            logger.info(f"Tavily returned {len(results)} results for query: {query[:50]}")
            return results
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Tavily rate limit hit")
        else:
            logger.error(f"Tavily API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return []

