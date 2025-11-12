"""Caching layer for web search results."""

from typing import Optional, List
from ...utils.cache import TTLCache
from ...models.web_search import WebSearchResult

# Cache with 5 minute TTL (configurable via env)
import os
from dotenv import load_dotenv

load_dotenv()

WEB_CACHE_TTL = int(os.getenv("WEB_CACHE_TTL", "300"))
_cache = TTLCache(ttl_sec=WEB_CACHE_TTL)


def get_cached_search(query: str, max_results: int) -> Optional[List[WebSearchResult]]:
    """Get cached search results."""
    key = f"web_search:{query}:{max_results}"
    return _cache.get(key)


def cache_search(query: str, max_results: int, results: List[WebSearchResult]) -> None:
    """Cache search results."""
    key = f"web_search:{query}:{max_results}"
    _cache.set(key, results)

