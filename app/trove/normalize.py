"""Normalize Trove API responses to consistent format."""

from typing import Any, Dict, Optional


def normalize_trove_id(article_data: Dict[str, Any]) -> Optional[str]:
    """Extract normalized article ID from Trove response."""
    return article_data.get("id") or article_data.get("troveUrl", "").split("/")[-1]


def normalize_trove_url(article_data: Dict[str, Any]) -> str:
    """Extract article URL."""
    return article_data.get("troveUrl", "")


def normalize_trove_title(article_data: Dict[str, Any]) -> str:
    """Extract article title."""
    heading = article_data.get("heading", {})
    if isinstance(heading, dict):
        return heading.get("title", "Untitled")
    return str(heading) if heading else "Untitled"


def normalize_trove_date(article_data: Dict[str, Any]) -> Optional[str]:
    """Extract publication date."""
    return article_data.get("date") or article_data.get("issued", {}).get("date", "")

