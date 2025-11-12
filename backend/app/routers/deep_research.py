from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
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


@router.get("/deep/markdown", response_class=PlainTextResponse)
async def deep_research_markdown(
    query: str = Query(..., min_length=1),
    years_from: int | None = Query(None),
    years_to: int | None = Query(None),
    max_sources: int = Query(12, ge=1, le=100),
    depth: str = Query("standard", pattern="^(brief|standard|deep)$"),
    region: str | None = Query(None),
):
    """Export deep research report as Markdown."""
    try:
        req = DeepResearchRequest(
            query=query,
            years_from=years_from,
            years_to=years_to,
            max_sources=max_sources,
            depth=depth,
            region=region,
        )
        result = await run_deep_research(req)
        
        # Convert to markdown
        lines = []
        lines.append(f"# Deep Research Report\n\n**Query:** {result.query}\n")
        lines.append(f"**Generated:** {result.generated_at}\n")
        lines.append("## Executive Summary\n")
        lines.append(result.executive_summary + "\n")
        
        if result.key_findings:
            lines.append("## Key Findings\n")
            for i, f in enumerate(result.key_findings, 1):
                lines.append(f"### {i}. {f.title}\n")
                lines.append(f"{f.insight}\n")
                if f.evidence:
                    lines.append("**Evidence:**")
                    for ev in f.evidence:
                        lines.append(f"> {ev}")
                if f.citations:
                    lines.append(f"**Citations:** {', '.join(f.citations)}\n")
                lines.append(f"**Confidence:** {f.confidence:.2f}\n")
        
        if result.timeline:
            lines.append("## Timeline\n")
            for t in result.timeline:
                date_str = t.date or "Unknown date"
                event_str = t.event
                cites_str = ", ".join(t.citations) if t.citations else ""
                lines.append(f"- **{date_str}:** {event_str}")
                if cites_str:
                    lines.append(f"  *Citations: {cites_str}*")
        
        if result.sources:
            lines.append("## Sources\n")
            for s in result.sources:
                line = f"- {s.title}"
                if s.year:
                    line += f" ({s.year})"
                if s.url:
                    line += f" — {s.url}"
                if s.relevance:
                    line += f" *[Relevance: {s.relevance:.2f}]*"
                lines.append(line)
        
        if result.methodology:
            lines.append("## Methodology\n")
            for m in result.methodology:
                lines.append(f"- {m}")
        
        if result.limitations:
            lines.append("## Limitations\n")
            for l in result.limitations:
                lines.append(f"- {l}")
        
        if result.next_questions:
            lines.append("## Next Questions\n")
            for q in result.next_questions:
                lines.append(f"- {q}")
        
        if result.stats:
            lines.append("## Statistics\n")
            for key, value in result.stats.items():
                lines.append(f"- **{key}:** {value}")
        
        return "\n".join(lines)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate markdown: {e}")


@router.get("/deep/evidence", response_class=StreamingResponse)
async def deep_research_evidence(
    query: str = Query(..., min_length=1),
    years_from: int | None = Query(None),
    years_to: int | None = Query(None),
    max_sources: int = Query(12, ge=1, le=100),
    depth: str = Query("standard", pattern="^(brief|standard|deep)$"),
    region: str | None = Query(None),
):
    """Export deep research evidence as JSONL."""
    try:
        req = DeepResearchRequest(
            query=query,
            years_from=years_from,
            years_to=years_to,
            max_sources=max_sources,
            depth=depth,
            region=region,
        )
        result = await run_deep_research(req)
        
        def gen():
            for s in result.sources:
                yield (
                    json.dumps({
                        "citation": s.id,
                        "title": s.title,
                        "year": s.year,
                        "url": s.url,
                        "snippets": s.snippets,
                        "relevance": s.relevance,
                        "type": s.type,
                    }, ensure_ascii=False) + "\n"
                ).encode("utf-8")
        
        return StreamingResponse(
            gen(),
            media_type="application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="evidence-{query[:50]}.jsonl"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate JSONL: {e}")

