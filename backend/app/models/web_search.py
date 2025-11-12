"""Data models for web search system."""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class RawSearchResult(BaseModel):
    """Raw search result from a provider (before content fetching)."""
    
    title: str
    url: str
    snippet: str
    date: Optional[str] = None  # Publication date if available
    provider: str  # Which provider returned this (tavily, serpapi, etc.)


class ExtractedContent(BaseModel):
    """Extracted content from a web page."""
    
    title: str
    text: str
    clean_html: Optional[str] = None
    extraction_method: str = "trafilatura"  # trafilatura, readability, or snippet


class WebSearchResult(BaseModel):
    """Complete web search result with extracted content and scoring."""
    
    title: str
    url: str
    snippet: str
    date: Optional[str] = None
    provider: str
    extracted_text: Optional[str] = None
    extracted_content: Optional[ExtractedContent] = None
    quotes: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    domain: str = ""  # Extracted domain from URL
    domain_reputation: float = 0.0  # Domain reputation score

