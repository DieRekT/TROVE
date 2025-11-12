"""Trove v3 API client for research evidence gathering."""

import logging
import os
from typing import List, Optional

import httpx
from dotenv import load_dotenv

from app.research.schemas import Evidence

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

TROVE_API_KEY = os.getenv("TROVE_API_KEY", "")
TROVE_BASE_URL = "https://api.trove.nla.gov.au/v3"


def search_trove(query: str, n: int = 20, include_article_text: bool = True) -> List[Evidence]:
    """
    Search Trove v3 API and return Evidence items.

    Args:
        query: Search query string
        n: Maximum number of results
        include_article_text: Whether to fetch full article text

    Returns:
        List of Evidence objects
    """
    if not TROVE_API_KEY:
        logger.warning("TROVE_API_KEY not set, skipping Trove search")
        return []

    params = {
        "q": query,
        "category": "newspaper",
        "encoding": "json",
        "reclevel": "full",
        "n": min(n, 20),  # API limit
    }

    if include_article_text:
        params["include"] = "articleText"

    headers = {"X-API-KEY": TROVE_API_KEY} if TROVE_API_KEY else {}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{TROVE_BASE_URL}/result", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        evidence_list = []
        # Parse Trove API response structure
        categories = data.get("category", [])
        if not categories or not isinstance(categories, list):
            logger.warning("No categories in Trove response")
            return []
        
        # Get first category (newspaper)
        category = categories[0] if isinstance(categories[0], dict) else {}
        records = category.get("records", {})
        if not isinstance(records, dict):
            logger.warning("Invalid records structure in Trove response")
            return []
        
        articles = records.get("article", [])
        if not isinstance(articles, list):
            logger.warning("No articles found in Trove response")
            return []

        for article in articles[:n]:
            try:
                if not isinstance(article, dict):
                    continue
                    
                # Extract heading - can be dict or string
                heading = article.get("heading", {})
                if isinstance(heading, dict):
                    title = heading.get("title", "Untitled")
                elif isinstance(heading, str):
                    title = heading
                else:
                    title = "Untitled"
                    
                url = article.get("troveUrl", "")
                date_str = article.get("date", "")
                snippet = article.get("snippet", "")

                # Try to get article text if available
                article_text = ""
                if include_article_text:
                    article_text = article.get("articleText", "")
                    if not article_text and "id" in article:
                        # Try fetching article text separately
                        article_id = article.get("id", "")
                        if article_id:
                            article_text = _fetch_article_text(article_id)

                # Use article text as snippet if available and longer
                if article_text and len(article_text) > len(snippet):
                    snippet = article_text[:500] + "..." if len(article_text) > 500 else article_text

                # Extract quotes (first 200 chars of snippet)
                quotes = [snippet[:200]] if snippet else []

                evidence = Evidence(
                    title=title,
                    url=url,
                    source="trove",
                    published_at=date_str,
                    snippet=snippet[:1000],  # Limit snippet length
                    quotes=quotes,
                    score=0.8,  # Default relevance score
                    rationale=f"Trove newspaper archive result for: {query}",
                )
                evidence_list.append(evidence)
            except Exception as e:
                logger.warning(f"Error processing Trove article: {e}")
                continue

        return evidence_list

    except Exception as e:
        logger.error(f"Trove API error: {e}")
        return []


def _fetch_article_text(article_id: str) -> str:
    """Fetch full article text by ID."""
    if not TROVE_API_KEY:
        return ""

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{TROVE_BASE_URL}/result",
                params={"q": f"id:{article_id}", "include": "articleText", "encoding": "json"},
                headers={"X-API-KEY": TROVE_API_KEY} if TROVE_API_KEY else {},
            )
            response.raise_for_status()
            data = response.json()
            articles = data.get("category", [{}])[0].get("records", {}).get("article", [])
            if articles:
                return articles[0].get("articleText", "")
    except Exception:
        pass

    return ""

