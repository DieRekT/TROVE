from __future__ import annotations
from fastapi import APIRouter, HTTPException
from ..models.deep_research import DeepResearchResponse
from ..services.structured_synthesis import synthesize_final

router = APIRouter(prefix="/api/research", tags=["synthesis"])

@router.post("/synthesize", response_model=DeepResearchResponse)
async def synthesize(report: DeepResearchResponse):
    try:
        final = synthesize_final(report)
        return final
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")

