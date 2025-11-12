"""Kingfisher card summarization."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def summarize_cards(cards: List[Dict[str, Any]]) -> str:
    """
    Summarize a list of Kingfisher cards into text.
    
    Args:
        cards: List of card dictionaries with type, title, content, metadata
    
    Returns:
        Summary text string
    """
    if not cards:
        return "No cards to summarize."
    
    # Group by type
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for card in cards:
        card_type = card.get("type", "object")
        if card_type not in by_type:
            by_type[card_type] = []
        by_type[card_type].append(card)
    
    # Build summary
    parts = []
    for card_type in ["quote", "event", "person", "place", "object"]:
        if card_type in by_type:
            items = by_type[card_type]
            parts.append(f"{card_type.capitalize()}s ({len(items)}):")
            for item in items[:3]:  # Show first 3
                title = item.get("title", "")
                content = item.get("content", "")[:100]
                parts.append(f"  - {title}: {content}...")
            if len(items) > 3:
                parts.append(f"  ... and {len(items) - 3} more")
    
    return "\n".join(parts) if parts else "Summary unavailable."

