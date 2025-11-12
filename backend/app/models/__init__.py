from .deep_research import (
    TimelineItem,
    Finding,
    SourceItem,
    DeepResearchRequest,
    DeepResearchResponse,
)

# Also import from parent models.py
import sys
from pathlib import Path
parent_models = Path(__file__).parent.parent / "models.py"
if parent_models.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("app_models", str(parent_models))
    app_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_models)
    NormalizedItem = app_models.NormalizedItem
    SearchResponse = app_models.SearchResponse
else:
    # Fallback if models.py doesn't exist
    from pydantic import BaseModel
    class NormalizedItem(BaseModel):
        id: str
        title: str
        snippet: str | None = None
    class SearchResponse(BaseModel):
        ok: bool = True
        q: str = ""
        page: int = 1
        page_size: int = 20
        total: int = 0
        items: list = []

__all__ = [
    "TimelineItem",
    "Finding",
    "SourceItem",
    "DeepResearchRequest",
    "DeepResearchResponse",
    "NormalizedItem",
    "SearchResponse",
]

