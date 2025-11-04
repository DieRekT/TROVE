
from pydantic import BaseModel


class NormalizedItem(BaseModel):
    id: str
    title: str
    snippet: str | None = None
    date: str | None = None
    type: str | None = None
    source: str = "Trove"
    url: str | None = None
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    ok: bool = True
    q: str
    page: int
    page_size: int
    total: int
    items: list[NormalizedItem]
