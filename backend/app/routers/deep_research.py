from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..models.deep_research import DeepResearchRequest, DeepResearchResponse
from ..services.deep_research import run_deep_research, run_deep_research_stream
from ..utils.telemetry import log_research_run


router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/deep", response_model=DeepResearchResponse)
async def deep_research(req: DeepResearchRequest):
    try:
        result = await run_deep_research(req)
        # Guardrail: reject empty reports
        if not result.sources or len(result.sources) == 0:
            # Log failed run
            log_research_run(
                query=req.query,
                years_from=req.years_from,
                years_to=req.years_to,
                max_sources=req.max_sources,
                depth=req.depth,
                sources_count=0,
                findings_count=len(result.key_findings),
                timeline_count=len(result.timeline),
                success=False,
                error="No sources found",
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "No evidence found. Try:\n"
                    "- Widening the year range (e.g., 1940-2000 instead of 1945-1980)\n"
                    "- Using more specific search terms (e.g., 'Iluka mineral sands rutile zircon' instead of 'Iluka mining')\n"
                    "- Checking that the query matches historical terminology used in Trove"
                )
            )
        
        # Log successful run
        log_research_run(
            query=req.query,
            years_from=req.years_from,
            years_to=req.years_to,
            max_sources=req.max_sources,
            depth=req.depth,
            sources_count=len(result.sources),
            findings_count=len(result.key_findings),
            timeline_count=len(result.timeline),
            success=True,
        )
        return result
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deep research failed: {e}")


@router.post("/deep/stream")
async def deep_research_stream(req: DeepResearchRequest):
    """Streaming endpoint using Server-Sent Events (SSE)."""
    async def generate():
        try:
            async for update in run_deep_research_stream(req):
                # Format as SSE
                data = json.dumps(update, ensure_ascii=False)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

