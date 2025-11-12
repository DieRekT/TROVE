"""SerpAPI search provider (secondary)."""

import logging
import os
from typing import List
import httpx
from dotenv import load_dotenv

from ....models.web_search import RawSearchResult

load_dotenv()

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_BASE_URL = "https://serpapi.com"


def search_serpapi(query: str, max_results: int = 12) -> List[RawSearchResult]:
    """
    Search using SerpAPI (Google engine).
    
    Returns list of RawSearchResult items.
    """
    if not SERPAPI_KEY:
        logger.debug("SERPAPI_KEY not set, skipping SerpAPI search")
        return []
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{SERPAPI_BASE_URL}/search",
                params={
                    "api_key": SERPAPI_KEY,
                    "q": query,
                    "engine": "google",
                    "num": max_results,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            organic_results = data.get("organic_results", [])
            for item in organic_results[:max_results]:
                results.append(
                    RawSearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", "")[:500],
                        date=item.get("date"),  # May not always be present
                        provider="serpapi",
                    )
                )
            
            logger.info(f"SerpAPI returned {len(results)} results for query: {query[:50]}")
            return results
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("SerpAPI rate limit hit")
        else:
            logger.error(f"SerpAPI error: {e}")
        return []
    except Exception as e:
        logger.error(f"SerpAPI search error: {e}")
        return []

