from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from ..services.trove_batch import ingest_trove


router = APIRouter(prefix="/api/research", tags=["seed"])


class SeedRequest(BaseModel):
    preset: str = "all"  # "all" or one of: iluka, croc, clarence
    state: str | None = None


PRESETS = {
    "iluka":   {"query": "Iluka mining mineral sands", "years_from": 1945, "years_to": 1980, "max_pages": 8, "state": "NSW"},
    "croc":    {"query": "Angourie crocodile",          "years_from": 1939, "years_to": 1939, "max_pages": 5, "state": "NSW"},
    "clarence":{"query": "mining in the Clarence Valley", "years_from": 1880, "years_to": 1955, "max_pages": 8, "state": "NSW"},
}


@router.post("/seed")
async def seed(req: SeedRequest) -> Dict[str, Any]:
    results = {}
    targets = PRESETS.keys() if req.preset == "all" else [req.preset]
    
    if req.preset not in PRESETS and req.preset != "all":
        raise HTTPException(status_code=400, detail=f"Invalid preset: {req.preset}. Must be one of: {', '.join(PRESETS.keys())}, all")
    
    for name in targets:
        cfg = PRESETS.get(name)
        if not cfg:
            continue
        if req.state:
            cfg = {**cfg, "state": req.state}
        # ingest directly (reuses your batch ingestion pipeline)
        total, used = await ingest_trove(
            query=cfg["query"],
            yfrom=cfg["years_from"],
            yto=cfg["years_to"],
            max_pages=cfg["max_pages"],
            page_size=100,
            state=cfg.get("state")
        )
        results[name] = {"retrieved": total, "indexed": used}
    
    return {"ok": True, "presets": list(targets), "stats": results}

