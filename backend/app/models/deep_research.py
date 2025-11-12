from __future__ import annotations
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, Field
from datetime import datetime


class TimelineItem(BaseModel):
    date: Optional[str] = None
    event: str
    citations: List[str] = []


class Finding(BaseModel):
    title: str
    insight: str
    evidence: List[str] = []
    citations: List[str] = []
    confidence: float = 0.65


class SourceItem(BaseModel):
    id: str
    title: str
    type: str
    year: Optional[int] = None
    url: Optional[str] = None
    snippets: List[str] = []
    relevance: float = 0.0


class DeepResearchRequest(BaseModel):
    query: str
    region: Optional[str] = None
    years_from: Optional[int] = None
    years_to: Optional[int] = None
    max_sources: int = 12
    depth: str = "standard"  # brief | standard | deep
    prefer_recent: bool = False  # Prefer recent evidence for web sources


class DeepResearchResponse(BaseModel):
    query: str
    executive_summary: str
    key_findings: List[Finding]
    timeline: List[TimelineItem]
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    sources: List[SourceItem]
    methodology: List[str]
    limitations: List[str]
    next_questions: List[str]
    stats: Dict[str, Union[float, int, str]] = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

