from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["text-tools"])


class TextRequest(BaseModel):
    text: str


@router.post("/explain")
async def explain_text(req: TextRequest):
    """Explain selected text (stub)."""
    return JSONResponse(content={
        "ok": True,
        "explanation": f"Explanation for: {req.text[:50]}..."
    })


@router.post("/define")
async def define_text(req: TextRequest):
    """Define selected term (stub)."""
    return JSONResponse(content={
        "ok": True,
        "definition": f"Definition for: {req.text[:50]}..."
    })


@router.post("/translate")
async def translate_text(req: TextRequest):
    """Translate text (stub)."""
    return JSONResponse(content={
        "ok": True,
        "translation": f"Translation for: {req.text[:50]}..."
    })

