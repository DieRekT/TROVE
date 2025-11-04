from pydantic import BaseModel


class ReadyResponse(BaseModel):
    ok: bool
    cache: str
