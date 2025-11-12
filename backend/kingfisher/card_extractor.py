"""Kingfisher card extraction from article text."""

import logging
from typing import Any, Dict, List, Optional

from .types import Card

logger = logging.getLogger(__name__)


def extract_cards_from_text(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    use_llm: bool = True,
) -> List[Card]:
    """
    Extract Kingfisher cards (quote/event/person/place/object) from article text.
    
    Args:
        text: Article text to extract cards from
        metadata: Optional article metadata (title, date, source)
        use_llm: Whether to use LLM extraction (falls back to extractive if False or unavailable)
    
    Returns:
        List of extracted Card objects
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for card extraction")
        return []
    
    # Content length guard - skip very long texts to avoid token limits
    if len(text) > 50000:  # ~50k chars, roughly 12k tokens
        logger.warning(f"Text too long ({len(text)} chars), truncating to 50000 chars")
        text = text[:50000]
    
    metadata = metadata or {}
    
    # Try LLM extraction if enabled
    if use_llm:
        try:
            return _extract_with_llm(text, metadata)
        except Exception as e:
            logger.warning(f"LLM extraction failed, falling back to extractive: {e}")
    
    # Fallback to extractive method
    return _extract_extractive(text, metadata)


def _extract_with_llm(text: str, metadata: Dict[str, Any]) -> List[Card]:
    """Extract cards using LLM (OpenAI)."""
    try:
        from openai import OpenAI
        
        # Check if API key is available
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        client = OpenAI(api_key=api_key)
        
        # Build prompt
        title = metadata.get("title", "Article")
        date = metadata.get("date", "")
        source = metadata.get("source", "")
        
        prompt = f"""Extract structured information cards from this historical newspaper article.

Article: {title}
Date: {date}
Source: {source}

Text:
{text[:40000]}  # Limit to ~10k tokens input

Extract cards of these types:
- quote: Notable quotes or statements
- event: Important events or occurrences
- person: People mentioned
- place: Locations mentioned
- object: Objects, items, or things mentioned

Return JSON array of cards, each with:
- type: one of quote/event/person/place/object
- title: short heading for the card
- content: the relevant text/excerpt
- metadata: any additional context

Example format:
[
  {{"type": "quote", "title": "Statement about X", "content": "exact quote text", "metadata": {{}}}},
  {{"type": "event", "title": "Event name", "content": "description", "metadata": {{"date": "..."}}}}
]

Return ONLY valid JSON, no markdown, no explanation."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for extraction
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured information from historical texts. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import json
        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        
        cards_data = json.loads(content)
        if not isinstance(cards_data, list):
            cards_data = [cards_data]
        
        # Convert to Card objects
        cards = []
        for item in cards_data:
            if isinstance(item, dict):
                cards.append(Card(
                    type=item.get("type", "object"),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    metadata=item.get("metadata", {})
                ))
        
        return cards
        
    except ImportError:
        logger.warning("OpenAI library not available, using extractive fallback")
        raise
    except Exception as e:
        logger.error(f"LLM extraction error: {e}")
        raise


def _extract_extractive(text: str, metadata: Dict[str, Any]) -> List[Card]:
    """
    Fallback extractive method - simple pattern-based extraction.
    Creates basic cards from text structure.
    """
    cards = []
    
    # Simple sentence-based extraction
    sentences = text.split(". ")
    
    # Extract quotes (text in quotes)
    import re
    quotes = re.findall(r'"([^"]+)"', text)
    for i, quote in enumerate(quotes[:5]):  # Limit to 5 quotes
        if len(quote) > 20:  # Only substantial quotes
            cards.append(Card(
                type="quote",
                title=f"Quote {i+1}",
                content=quote,
                metadata={"extracted": "extractive"}
            ))
    
    # Extract place names (capitalized words that might be places)
    # This is very basic - LLM is much better
    place_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
    potential_places = set(re.findall(place_pattern, text[:1000]))  # First 1000 chars
    # Filter common non-places
    common_words = {"The", "This", "That", "They", "There", "These", "Those"}
    places = [p for p in potential_places if p not in common_words and len(p) > 3][:5]
    for place in places:
        cards.append(Card(
            type="place",
            title=place,
            content=f"Mentioned in: {metadata.get('title', 'article')}",
            metadata={"extracted": "extractive"}
        ))
    
    # If no cards extracted, create a generic one
    if not cards:
        cards.append(Card(
            type="object",
            title=metadata.get("title", "Article Content"),
            content=text[:500] + "..." if len(text) > 500 else text,
            metadata={"extracted": "extractive", "fallback": True}
        ))
    
    return cards

