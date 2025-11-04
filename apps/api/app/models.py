
from pydantic import BaseModel


class SearchQuery(BaseModel):
    q: str
    n: int = 20
    date_from: str | None = None  # "YYYY-MM-DD"
    date_to: str | None = None
    state: str | None = None
    sensitive_mode: bool = False


class ArticleRequest(BaseModel):
    id_or_url: str
    pdf: bool = False


class SummaryRequest(BaseModel):
    text: str
    max_words: int = 180

