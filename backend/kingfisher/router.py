"""Kingfisher API router for card extraction endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from .card_extractor import extract_cards_from_text
from .types import Card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kingfisher", tags=["kingfisher"])


class ExtractCardsRequest(BaseModel):
    """Request model for card extraction."""
    text: str = Field(..., min_length=1, description="Article text to extract cards from")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Article metadata (title, date, source)")
    use_llm: bool = Field(default=True, description="Use LLM extraction (falls back to extractive if False)")


class ExtractCardsResponse(BaseModel):
    """Response model for card extraction."""
    ok: bool = Field(default=True)
    cards: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted cards")
    count: int = Field(default=0, description="Number of cards extracted")
    method: str = Field(default="llm", description="Extraction method used: llm or extractive")


class ExtractBatchRequest(BaseModel):
    """Request model for batch card extraction."""
    items: List[ExtractCardsRequest] = Field(..., min_items=1, max_items=10, description="List of texts to extract cards from")


@router.post("/extract-cards", response_model=ExtractCardsResponse)
async def extract_cards_endpoint(request: ExtractCardsRequest) -> ExtractCardsResponse:
    """
    Extract Kingfisher cards from a single article text.
    
    Returns cards of types: quote, event, person, place, object
    """
    try:
        # Empty input guard
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Content length guard
        if len(request.text) > 100000:  # 100k chars limit
            raise HTTPException(
                status_code=400,
                detail=f"Text too long ({len(request.text)} chars). Maximum 100,000 characters."
            )
        
        # Extract cards
        try:
            cards = extract_cards_from_text(
                request.text,
                metadata=request.metadata,
                use_llm=request.use_llm
            )
            method = "llm" if request.use_llm else "extractive"
        except Exception as e:
            logger.error(f"Card extraction failed: {e}")
            # Fallback to extractive if LLM fails
            if request.use_llm:
                logger.info("Falling back to extractive method")
                cards = extract_cards_from_text(
                    request.text,
                    metadata=request.metadata,
                    use_llm=False
                )
                method = "extractive"
            else:
                raise HTTPException(status_code=500, detail=f"Card extraction failed: {str(e)}")
        
        # Convert cards to dicts
        cards_data = [card.model_dump() for card in cards]
        
        return ExtractCardsResponse(
            ok=True,
            cards=cards_data,
            count=len(cards_data),
            method=method
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in extract-cards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/extract-batch", response_model=Dict[str, Any])
async def extract_batch_endpoint(request: ExtractBatchRequest) -> Dict[str, Any]:
    """
    Extract cards from multiple texts in batch.
    
    Processes up to 10 items. Returns results for each item.
    """
    try:
        results = []
        
        for i, item in enumerate(request.items):
            try:
                # Empty input guard
                if not item.text or not item.text.strip():
                    results.append({
                        "index": i,
                        "ok": False,
                        "error": "Text cannot be empty",
                        "cards": [],
                        "count": 0
                    })
                    continue
                
                # Content length guard
                if len(item.text) > 100000:
                    results.append({
                        "index": i,
                        "ok": False,
                        "error": f"Text too long ({len(item.text)} chars)",
                        "cards": [],
                        "count": 0
                    })
                    continue
                
                # Extract cards
                try:
                    cards = extract_cards_from_text(
                        item.text,
                        metadata=item.metadata,
                        use_llm=item.use_llm
                    )
                    method = "llm" if item.use_llm else "extractive"
                except Exception as e:
                    logger.warning(f"Extraction failed for item {i}, falling back: {e}")
                    # Fallback to extractive
                    if item.use_llm:
                        cards = extract_cards_from_text(
                            item.text,
                            metadata=item.metadata,
                            use_llm=False
                        )
                        method = "extractive"
                    else:
                        raise
                
                cards_data = [card.model_dump() for card in cards]
                
                results.append({
                    "index": i,
                    "ok": True,
                    "cards": cards_data,
                    "count": len(cards_data),
                    "method": method
                })
                
            except Exception as e:
                logger.error(f"Error processing batch item {i}: {e}")
                results.append({
                    "index": i,
                    "ok": False,
                    "error": str(e),
                    "cards": [],
                    "count": 0
                })
        
        return {
            "ok": True,
            "results": results,
            "total": len(results),
            "successful": sum(1 for r in results if r.get("ok"))
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in extract-batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

