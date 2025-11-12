"""Main web search aggregator coordinating all providers."""

import asyncio
import logging
from typing import List, Optional
from urllib.parse import urlparse
import time

from ..models.web_search import RawSearchResult, WebSearchResult, ExtractedContent
from .web.providers import (
    search_tavily,
    search_serpapi,
    search_duckduckgo,
    search_searxng,
)
from .web.fetcher import fetch_and_extract
from .web.synth.quotes import extract_quotes
from .web.ranking.score import calculate_relevance_score
from .web.cache import get_cached_search, cache_search

logger = logging.getLogger(__name__)

# Provider priority order
PROVIDERS = [
    ("tavily", search_tavily),
    ("serpapi", search_serpapi),
    ("duckduckgo", search_duckduckgo),
    ("searxng", search_searxng),
]


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _deduplicate_results(results: List[WebSearchResult]) -> List[WebSearchResult]:
    """Remove duplicate results based on URL."""
    seen_urls = set()
    unique = []
    for result in results:
        url_normalized = result.url.lower().rstrip("/")
        if url_normalized not in seen_urls:
            seen_urls.add(url_normalized)
            unique.append(result)
    return unique


async def search_web(
    query: str,
    max_results: int = 12,
    timeout: float = 22.0,
    prefer_recent: bool = False,
    fetch_content: bool = True,
) -> List[WebSearchResult]:
    """
    Search web using multiple providers with graceful degradation.
    
    Provider priority: Tavily → SerpAPI → DuckDuckGo → SearxNG
    - Tries providers in order until we have enough results
    - Fetches content for top results (concurrent, max 4)
    - Extracts quotes and scores results
    - Error budget: Total time ≤ timeout (default 22s)
    
    Returns sorted list of WebSearchResult (by relevance_score desc).
    """
    start_time = time.time()
    
    # Check cache first
    try:
        cached = get_cached_search(query, max_results)
        if cached:
            logger.info(f"Cache hit for query: {query[:50]}")
            return cached
    except Exception as e:
        logger.warning(f"Cache check failed: {e}, continuing with search")
    
    # Collect raw results from providers (run sync providers in executor)
    all_raw_results: List[RawSearchResult] = []
    seen_urls = set()
    
    # Try providers in priority order (run sync functions in thread pool)
    loop = asyncio.get_event_loop()
    
    for provider_name, provider_func in PROVIDERS:
        elapsed = time.time() - start_time
        if elapsed >= timeout * 0.8:  # Reserve 20% time for content fetching
            logger.warning(f"Timeout approaching, stopping provider collection")
            break
        
        if len(all_raw_results) >= max_results * 2:  # Collect extra for deduplication
            break
        
        try:
            # Run sync provider function in thread pool
            provider_results = await loop.run_in_executor(
                None, provider_func, query, max_results * 2
            )
            
            # Deduplicate by URL
            for result in provider_results:
                url_normalized = result.url.lower().rstrip("/")
                if url_normalized not in seen_urls:
                    seen_urls.add(url_normalized)
                    all_raw_results.append(result)
            
            logger.info(f"{provider_name} returned {len(provider_results)} results")
            
        except Exception as e:
            logger.warning(f"Provider {provider_name} failed: {e}")
            continue  # Graceful degradation
    
    if not all_raw_results:
        logger.warning(f"No results from any provider for query: {query[:50]}")
        return []
    
    # Convert to WebSearchResult
    web_results: List[WebSearchResult] = []
    for raw in all_raw_results[:max_results * 2]:  # Limit before fetching
        web_results.append(
            WebSearchResult(
                title=raw.title,
                url=raw.url,
                snippet=raw.snippet,
                date=raw.date,
                provider=raw.provider,
                domain=_extract_domain(raw.url),
            )
        )
    
    # Fetch content for top results (concurrent, max 4)
    if fetch_content:
        fetch_count = min(4, len(web_results))
        fetch_tasks = []
        
        for result in web_results[:fetch_count]:
            # Run sync fetch_and_extract in thread pool
            loop = asyncio.get_event_loop()
            import os
            timeout = int(os.getenv("WEB_FETCH_TIMEOUT_SECONDS", "20"))
            fetch_tasks.append(
                loop.run_in_executor(None, fetch_and_extract, result.url, timeout)
            )
        
        # Run fetches concurrently
        fetched_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        for i, fetched in enumerate(fetched_results):
            if isinstance(fetched, Exception):
                logger.warning(f"Content fetch failed for {web_results[i].url}: {fetched}")
                continue
            
            if fetched:
                web_results[i].extracted_content = fetched
                web_results[i].extracted_text = fetched.text
    
    # Extract query terms for scoring
    import re
    query_terms = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if w and len(w) > 2]
    
    # Extract quotes from extracted text or snippet
    seen_domains: dict = {}
    for result in web_results:
        # Extract quotes
        text_for_quotes = result.extracted_text or result.snippet
        if text_for_quotes:
            quotes = extract_quotes(text_for_quotes, query_terms, max_quotes=2)
            result.quotes = quotes
        
        # Calculate relevance score
        result.relevance_score = calculate_relevance_score(
            result,
            query,
            query_terms,
            prefer_recent=prefer_recent,
            seen_domains=seen_domains,
        )
    
    # Sort by relevance score
    web_results.sort(key=lambda r: r.relevance_score, reverse=True)
    
    # Deduplicate and limit
    web_results = _deduplicate_results(web_results)
    web_results = web_results[:max_results]
    
    # Cache results
    try:
        cache_search(query, max_results, web_results)
    except Exception as e:
        logger.warning(f"Failed to cache results: {e}")
    
    elapsed = time.time() - start_time
    logger.info(f"Web search completed in {elapsed:.2f}s, returned {len(web_results)} results")
    
    return web_results



