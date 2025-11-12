"""Pydantic schemas for Deep Research system."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ResearchStart(BaseModel):
    """Request to start a research job."""

    question: str = Field(..., description="The research question")
    region: Optional[str] = Field(None, description="Geographic region filter (e.g., 'Clarence Valley, NSW')")
    time_window: Optional[str] = Field(None, description="Time period (e.g., '1970-1995' or 'last 5 years')")
    sources: List[str] = Field(default_factory=list, description="Source types to include: 'web', 'trove'")
    depth: Literal["brief", "standard", "deep"] = Field(default="standard", description="Research depth level")


class Evidence(BaseModel):
    """Evidence item from web or Trove sources."""

    title: str
    url: str
    source: str = Field(..., description="Source identifier: 'web' or 'trove'")
    published_at: Optional[str] = None
    snippet: str
    quotes: List[str] = Field(default_factory=list, description="Relevant quoted passages")
    score: float = Field(default=0.0, description="Relevance score (0-1)")
    rationale: str = Field(default="", description="Why this evidence is relevant")


class PlanStep(BaseModel):
    """A single step in the research plan."""

    query: str = Field(..., description="Search query for this step")
    rationale: str = Field(..., description="Why this step is needed")
    scope: Literal["web", "trove"] = Field(..., description="Where to search")


class Job(BaseModel):
    """Research job status and metadata."""

    id: str
    status: Literal["queued", "running", "done", "error"] = "queued"
    created_at: datetime
    updated_at: datetime
    progress_pct: int = Field(default=0, ge=0, le=100)
    summary_path: Optional[str] = None
    evidence_path: Optional[str] = None
    question: str = ""
    error_message: Optional[str] = None


class Citation(BaseModel):
    """Citation for findings report."""

    title: str
    url: str
    source: str


class Findings(BaseModel):
    """Synthesized research findings."""

    overview: str = Field(..., description="5-8 sentence overview")
    key_points: List[str] = Field(..., description="6-10 key points with source tags")
    limitations: List[str] = Field(default_factory=list, description="Research limitations")
    next_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    citations: List[Citation] = Field(default_factory=list, description="All cited sources")

