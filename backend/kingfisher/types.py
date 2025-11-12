"""Kingfisher card types."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class Card(BaseModel):
    """Kingfisher card representing extracted information from articles."""
    
    type: str = Field(..., description="Card type: quote, event, person, place, object")
    title: str = Field(..., description="Card title/heading")
    content: str = Field(..., description="Card content/text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

