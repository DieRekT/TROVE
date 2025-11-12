from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/item", tags=["items"])


@router.get("/{item_id}")
async def get_item(item_id: str):
    """Get article details (stub)."""
    return JSONResponse(content={
        "ok": True,
        "id": item_id,
        "title": "Article Title",
        "date": None,
        "source": None,
        "text": "",
        "url": f"https://trove.nla.gov.au/newspaper/article/{item_id}" if item_id.isdigit() else item_id
    })


@router.get("/{item_id}/images")
async def get_item_images(item_id: str):
    """Get article images (stub)."""
    return JSONResponse(content={"ok": True, "images": []})


@router.post("/{item_id}/refresh-images")
async def refresh_item_images(item_id: str):
    """Refresh article images (stub)."""
    return JSONResponse(content={"ok": True, "message": "Images refreshed"})

