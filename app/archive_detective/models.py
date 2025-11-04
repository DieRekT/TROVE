from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Property(BaseModel):
    address: str
    alias: str | None = None
    legal: dict
    parish: str | None = None
    county: str | None = None
    state: str | None = None
    country: str | None = None


class TroveQuery(BaseModel):
    label: str
    query: str
    trove_zone: Literal[
        "newspaper",
        "gazette",
        "magazine",
        "book",
        "image",
        "research",
        "diary",
        "music",
        "list",
        "people",
        "all",
    ] = "newspaper"
    date_from: str = Field(default="1860-01-01")
    date_to: str = Field(default="1970-12-31")
    notes: str = ""
