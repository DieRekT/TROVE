"""SearxNG search provider (fallback/self-hosted)."""

import logging
import os
from typing import List
import httpx
from dotenv import load_dotenv

from ....models.web_search import RawSearchResult

load_dotenv()

logger = logging.getLogger(__name__)

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")


def search_searxng(query: str, max_results: int = 12) -> List[RawSearchResult]:
    """
    Search using SearxNG instance (self-hosted fallback).
    
    Returns list of RawSearchResult items.
    """
    if not SEARXNG_URL or SEARXNG_URL == "http://localhost:8080":
        # Only try if explicitly configured
        logger.debug("SEARXNG_URL not configured or default, skipping")
        return []
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "engines": "google,bing,duckduckgo",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    RawSearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:500],
                        date=item.get("publishedDate"),  # May not be present
                        provider="searxng",
                    )
                )
            
            logger.info(f"SearxNG returned {len(results)} results for query: {query[:50]}")
            return results
            
    except httpx.ConnectError:
        logger.warning(f"SearxNG instance not available at {SEARXNG_URL}")
        return []
    except Exception as e:
        logger.warning(f"SearxNG search error: {e}")
        return []

