from __future__ import annotations
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/trove", tags=["mobile"])

# Proxy to Archive Detective API (port 8001)
MOBILE_API_BASE = "http://127.0.0.1:8001"


class SearchRequest(BaseModel):
    q: str
    n: int = 20
    sensitive_mode: bool = False
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    state: Optional[str] = None


@router.post("/search")
async def proxy_search(req: SearchRequest):
    """Proxy search requests to Archive Detective API (port 8001)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MOBILE_API_BASE}/api/trove/search",
                json=req.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Archive Detective API unavailable: {str(e)}")


@router.get("/article")
async def proxy_article(
    id_or_url: str = Query(...),
    pdf: bool = False
):
    """Proxy article requests to Archive Detective API (port 8001)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MOBILE_API_BASE}/api/trove/article",
                params={"id_or_url": id_or_url, "pdf": pdf}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Archive Detective API unavailable: {str(e)}")

