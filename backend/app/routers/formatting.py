from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from typing import Iterator
from ..models.deep_research import DeepResearchResponse
from ..utils.markdown import render_markdown
from ..utils.jsonl import to_jsonl


router = APIRouter(prefix="/api/research", tags=["formatting"])


class ResearchPayload(BaseModel):
    report: DeepResearchResponse


@router.post("/markdown", response_class=PlainTextResponse)
async def to_markdown(payload: ResearchPayload):
    return render_markdown(payload.report)


@router.post("/evidence")
async def evidence_jsonl(payload: ResearchPayload):
    lines: Iterator[str] = to_jsonl(
        ({"citation": s.id, "source": s.dict()} for s in payload.report.sources)
    )
    return StreamingResponse(lines, media_type="application/jsonl")

