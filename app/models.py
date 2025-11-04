"""Pydantic models for data structures."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SearchParams(BaseModel):
    """Parameters for Trove search."""

    q: str = Field(default="", description="Search query string")
    category: Literal[
        "newspaper",
        "magazine",
        "book",
        "image",
        "research",
        "diary",
        "music",
        "list",
        "people",
        "all",
    ] = Field(default="newspaper", description="Content category")
    n: int = Field(default=20, ge=1, le=100, description="Number of results")
    s: int = Field(default=0, ge=0, description="Start offset")
    show_images: bool = Field(default=True, description="Show image thumbnails")
    l_format: str | None = Field(default=None, description="Format filter (e.g., Photograph, Map)")
    l_artType: str | None = Field(default=None, description="Art type filter")
    l_place: str | None = Field(default=None, description="Place filter")
    sortby: Literal["relevance", "dateAsc", "dateDesc"] | None = Field(
        default=None, description="Sort order"
    )


class ImageLinks(BaseModel):
    """Image URL links."""

    thumbnail: HttpUrl | None = None
    full: HttpUrl | None = None


class TroveRecord(BaseModel):
    """Normalized Trove record for display."""

    category: str
    id: str | None = None  # Trove item ID extracted from URL or record
    title: str | None = None
    subtitle: str | None = None
    issued: str | None = None
    publisher_or_source: str | None = None
    trove_url: str | None = None  # Keep as string for flexibility
    snippet: str | None = None
    image_thumb: str | None = None
    image_full: str | None = None


class SearchResponse(BaseModel):
    """Search response data."""

    query: str
    category: str
    total: int = 0
    items: list[TroveRecord] = Field(default_factory=list)
    page_size: int
    offset: int
    can_paginate: bool
    prev_offset: int = 0
    next_offset: int = 0
