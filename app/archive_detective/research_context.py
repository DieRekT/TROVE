"""Research context tracking - stores articles for AI reference."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Optional SQLite write-through
try:
    from ..context_store import upsert_item as _sqlite_upsert
    _persist_enabled = True
except Exception:
    _persist_enabled = False

# In-memory storage for research context (session-based)
# In production, use Redis or database
_research_context: dict[str, list[dict[str, Any]]] = {}

# Maximum articles to keep in context per session
MAX_CONTEXT_ARTICLES = 50


def add_article_to_context(session_key: str, article: dict[str, Any]) -> None:
    """Add an article to the research context for a session."""
    if session_key not in _research_context:
        _research_context[session_key] = []
    
    # Avoid duplicates - check if article ID already exists
    article_id = article.get("id") or article.get("article_id")
    if article_id:
        # Remove existing entry with same ID
        _research_context[session_key] = [
            a for a in _research_context[session_key]
            if (a.get("id") or a.get("article_id")) != article_id
        ]
    
    # Add to front of list (most recent first)
    _research_context[session_key].insert(0, {
        "id": article.get("id") or article.get("article_id"),
        "title": article.get("title", "Untitled"),
        "date": article.get("date") or article.get("issued"),
        "source": article.get("source") or article.get("publisher_or_source"),
        "snippet": article.get("snippet", "")[:500],  # First 500 chars
        "text": article.get("text", "")[:2000],  # First 2000 chars for context
        "url": article.get("url") or article.get("trove_url"),
        "category": article.get("category", "unknown"),
    })
    
    # Limit to MAX_CONTEXT_ARTICLES
    if len(_research_context[session_key]) > MAX_CONTEXT_ARTICLES:
        _research_context[session_key] = _research_context[session_key][:MAX_CONTEXT_ARTICLES]
    
    logger.info(f"Added article {article_id} to context for session {session_key[:20]}")
    
    # Optional: write through to SQLite for persistence
    if _persist_enabled:
        try:
            _sqlite_upsert(session_key, article)
        except Exception as e:
            logger.warning(f"Failed to persist to SQLite: {e}")


def get_research_context(session_key: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get research context (recent articles) for a session."""
    return _research_context.get(session_key, [])[:limit]


def format_context_for_llm(articles: list[dict[str, Any]]) -> str:
    """Format article context for inclusion in LLM prompt."""
    if not articles:
        return ""
    
    context_parts = []
    context_parts.append(f"\n\nRESEARCH CONTEXT - You have access to {len(articles)} recently viewed articles:")
    
    for i, article in enumerate(articles, 1):
        parts = []
        if article.get("title"):
            parts.append(f"Title: {article['title']}")
        if article.get("date"):
            parts.append(f"Date: {article['date']}")
        if article.get("source"):
            parts.append(f"Source: {article['source']}")
        if article.get("snippet"):
            parts.append(f"Snippet: {article['snippet'][:300]}")
        if article.get("text"):
            parts.append(f"Content: {article['text'][:1000]}")
        if article.get("url"):
            parts.append(f"URL: {article['url']}")
        if article.get("id"):
            parts.append(f"ID: {article['id']}")
        
        context_parts.append(f"\n--- Article {i} ---")
        context_parts.append("\n".join(parts))
        context_parts.append("")
    
    context_parts.append("\nWhen answering questions, reference these articles by their titles, dates, or content.")
    context_parts.append("You can mention specific details from these articles in your responses.")
    context_parts.append("If asked about something not in these articles, say so and suggest searching for more information.\n")
    
    return "\n".join(context_parts)


def clear_context(session_key: str) -> None:
    """Clear research context for a session."""
    if session_key in _research_context:
        del _research_context[session_key]
        logger.info(f"Cleared context for session {session_key[:20]}")

