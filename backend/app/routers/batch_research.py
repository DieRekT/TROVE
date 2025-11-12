from __future__ import annotations
import asyncio
import json
import time
import uuid
import re
import sqlite3
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from ..db import get_conn
from ..services.trove_batch import ingest_trove, sentence_quotes
from ..services.quotes import best_sentences
from ..services.ranking import bm25_to_score, title_overlap, date_proximity, blend
from ..services.geo import nsw_bonus_for_text, infer_state_from_query


router = APIRouter(prefix="/api/research", tags=["batch"])


def infer_state(q: str) -> str | None:
    ql = q.lower()
    # WA triggers
    if any(k in ql for k in ["western australia", " iluka resources", "eneabba", "capel", "narngulu", "geraldton", "bunbury", "perth"]):
        return "Western Australia"
    # NSW default if clarence/sandon/yamba/iluka context
    if any(k in ql for k in ["clarence", "sandon", "yamba", "angourie", "iluka", "evans head", "ballina", "tweed", "lismore"]):
        return "New South Wales"
    return None

class StartJob(BaseModel):
    query: str
    years_from: Optional[int] = None
    years_to: Optional[int] = None
    max_pages: int = 10
    page_size: int = 100
    max_sources_for_report: int = 20
    state: str | None = None  # "New South Wales" or "Western Australia"


def _terms(q: str) -> List[str]:
    """Extract search terms from query."""
    return [w for w in re.split(r'[^a-z0-9]+', q.lower()) if w and len(w) > 2]


@router.post("/start-batch")
async def start_batch(req: StartJob):
    """Start a background batch ingestion job."""
    job_id = str(uuid.uuid4())
    now = time.time()
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs(id,query,years_from,years_to,max_pages,state,status,progress,created_at,updated_at) VALUES(?,?,?,?,?,?,'queued',0,?,?)",
            (job_id, req.query, req.years_from, req.years_to, req.max_pages, req.state, now, now)
        )
    
    async def worker():
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                    (time.time(), job_id)
                )
            
            state = req.state or infer_state(req.query)
            retrieved, stored = await ingest_trove(
                req.query,
                req.years_from,
                req.years_to,
                req.max_pages,
                req.page_size,
                job_id=job_id,
                state=state
            )
            
            with get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET status='done', progress=1.0, updated_at=?, error=NULL WHERE id=?",
                    (time.time(), job_id)
                )
        except Exception as e:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET status='error', error=?, updated_at=? WHERE id=?",
                    (str(e), time.time(), job_id)
                )
    
    asyncio.create_task(worker())
    return {"job_id": job_id, "status": "queued"}


@router.get("/job/{job_id}")
def job_status(job_id: str):
    """Get job status."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return dict(row)


@router.get("/job/{job_id}/report")
def job_report(job_id: str, max_sources: int = 20):
    """Build a verified report from indexed evidence."""
    with get_conn() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "job not found")
        if job["status"] != "done":
            raise HTTPException(409, "job not complete")
        
        # Pull top-N by FTS match
        q = job["query"]
        terms = _terms(q)
        
        # FTS search - match query terms with BM25 ranking
        # Build FTS query: each term must appear (AND) or use OR for flexibility
        query_terms = " OR ".join(terms)
        # Try BM25 first, fallback to simple match if BM25 not available
        try:
            rows = conn.execute("""
                SELECT s.id, s.title, s.year, s.url, s.text, s.raw, bm25(sources_fts) AS rank
                FROM sources_fts
                JOIN sources s ON s.id = sources_fts.id
                WHERE sources_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query_terms, max_sources)).fetchall()
        except sqlite3.OperationalError:
            # Fallback if BM25 not available (older SQLite)
            rows = conn.execute("""
                SELECT s.id, s.title, s.year, s.url, s.text, s.raw, 0.0 AS rank
                FROM sources_fts
                JOIN sources s ON s.id = sources_fts.id
                WHERE sources_fts MATCH ?
                LIMIT ?
            """, (query_terms, max_sources)).fetchall()
        
        # Get BM25 ranks for normalization (lower is better in FTS5)
        ranks = [float(r["rank"]) for r in rows] if rows else []
        
        # Normalize BM25 scores using min-max normalization across all results
        from ..services.ranking import normalize_bm25_scores
        normalized_bm25 = normalize_bm25_scores(ranks) if ranks else []
        
        sources = []
        # Use state from job if available, otherwise infer from query
        # job is a sqlite3.Row, access with [] not .get()
        requested_state = (job["state"] if job["state"] else None) or infer_state(q)
        for idx, r in enumerate(rows):
            raw = None
            try:
                raw_text = r.get("raw")
                if raw_text:
                    if isinstance(raw_text, bytes):
                        raw = json.loads(raw_text.decode("utf-8"))
                    else:
                        raw = json.loads(raw_text)
            except Exception:
                raw = None
            # If a state is implied/requested, discard obvious mismatches
            if requested_state and raw:
                st = None
                # trove often exposes state under title.state or title.title like '... (W.A.)'
                tmeta = raw.get("title") or {}
                st = tmeta.get("state") or None
                if not st:
                    ttxt = (tmeta.get("title") or "")
                    if "(W.A.)" in ttxt: st = "Western Australia"
                    if "(N.S.W.)" in ttxt: st = "New South Wales"
                if st and st != requested_state:
                    continue
            # Use improved quote extraction
            text_for_quotes = r["text"] or ""
            quotes = best_sentences(text_for_quotes, terms, k=2) if text_for_quotes else []
            
            # Calculate blended relevance score using normalized BM25
            bm25_raw = float(r["rank"]) if idx < len(ranks) else 0.0
            bm25_normalized = normalized_bm25[idx] if idx < len(normalized_bm25) else 0.0
            tb = title_overlap(r["title"] or "", terms)
            dp = date_proximity(r["year"], job.get("years_from"), job.get("years_to"))
            text_for_bonus = " ".join([r["title"] or "", text_for_quotes])
            nswb = nsw_bonus_for_text(text_for_bonus)
            rel = blend(bm25_normalized, tb, dp, nswb)
            
            sources.append({
                "id": r["id"],
                "title": r["title"],
                "year": r["year"],
                "url": r["url"],
                "snippets": quotes,
                "relevance": round(rel, 3),
                "bm25": bm25_raw  # Keep raw for debugging
            })
        
        if not sources:
            raise HTTPException(422, "No evidence found in index for this job.")
        
        # Sort sources by relevance (already sorted, but ensure)
        sources.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Build findings with improved quotes and insights
        findings = []
        timeline = []
        
        for s in sources[:5]:
            # Extract top terms that appear in title
            title_lower = (s["title"] or "").lower()
            top_terms = [t for t in terms if t in title_lower][:3]
            insight = s["title"] or "Untitled"
            if top_terms:
                insight = f"{s['title']} mentions {', '.join(top_terms)}."
            
            findings.append({
                "title": s["title"] or "Untitled",
                "insight": insight,
                "evidence": s["snippets"],
                "citations": [s["id"]],
                "confidence": min(0.9, 0.6 + 0.3 * s["relevance"])
            })
            
            # Timeline with actual dates if available
            if s["year"]:
                # Try to parse actual date from raw data if available
                date_str = f"{s['year']:04d}-01-01"  # Default fallback
                try:
                    raw_text = r.get("raw") if 'r' in locals() else None
                    if raw_text:
                        if isinstance(raw_text, bytes):
                            raw = json.loads(raw_text.decode("utf-8"))
                        else:
                            raw = json.loads(raw_text)
                        # Try to get actual date from Trove record
                        trove_date = raw.get("date") or raw.get("issued")
                        if trove_date:
                            # Parse YYYY-MM-DD or YYYY format
                            import re
                            date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(trove_date))
                            if date_match:
                                date_str = trove_date
                            elif re.search(r'\d{4}', str(trove_date)):
                                date_str = f"{s['year']:04d}-01-01"
                except Exception:
                    pass  # Fall back to default
                
                timeline.append({
                    "date": date_str,
                    "event": (s["title"] or "")[:120],
                    "citations": [s["id"]]
                })
        
        # Generate executive summary using improved summarizer
        try:
            from ..services.summarize_exec import exec_summary as exec_summary_func
            executive = exec_summary_func(q, findings, timeline)
        except Exception:
            executive = f"This report compiles Trove evidence for '{q}'. Found {len(sources)} relevant sources."
        
        resp = {
            "query": q,
            "executive_summary": executive,
            "key_findings": findings,
            "timeline": timeline,
            "entities": {"places": [], "organisations": [], "topics": []},
            "sources": sources,
            "methodology": ["batch trove ingest", "SQLite FTS5", "sentence quotes", "timeline synthesis"],
            "limitations": ["no cross-archive corroboration yet", "light ranking"],
            "next_questions": ["Which claims require independent confirmation?"],
            "stats": {"used": len(sources)}
        }
        
        return JSONResponse(resp)


@router.get("/job/{job_id}/markdown", response_class=PlainTextResponse)
def job_markdown(job_id: str, max_sources: int = 20):
    """Export report as Markdown."""
    r = job_report(job_id, max_sources=max_sources).body
    if isinstance(r, bytes):
        data = json.loads(r.decode("utf-8"))
    elif isinstance(r, (str, bytearray)):
        data = json.loads(r)
    else:
        # Handle memoryview or other types
        data = json.loads(bytes(r).decode("utf-8"))
    
    lines = []
    lines.append(f"# Deep Research Report\n\n**Query:** {data['query']}\n")
    lines.append("## Executive Summary\n" + data["executive_summary"] + "\n")
    lines.append("## Key Findings")
    
    for i, f in enumerate(data["key_findings"], 1):
        lines.append(f"### {i}. {f['title']}\n{f['insight']}")
        for q in f.get("evidence", []):
            lines.append(f"> {q}")
        lines.append("**Citations:** " + ", ".join(f.get("citations", [])))
        lines.append("")
    
    if data.get("timeline"):
        lines.append("## Timeline")
        for t in data["timeline"]:
            lines.append(f"- {t['date']}: {t['event']} ({', '.join(t.get('citations', []))})")
    
    if data.get("sources"):
        lines.append("## Sources")
        for s in data["sources"]:
            line = f"- {s['title']}"
            if s.get("url"):
                line += f" — {s['url']}"
            if s.get("year"):
                line += f" — {s['year']}"
            lines.append(line)
    
    return "\n".join(lines)


@router.get("/job/{job_id}/evidence")
def job_evidence(job_id: str, max_sources: int = 20):
    """Export evidence as JSONL."""
    r = job_report(job_id, max_sources=max_sources).body
    if isinstance(r, bytes):
        data = json.loads(r.decode("utf-8"))
    elif isinstance(r, (str, bytearray)):
        data = json.loads(r)
    else:
        # Handle memoryview or other types
        data = json.loads(bytes(r).decode("utf-8"))
    
    def gen():
        for s in data.get("sources", []):
            yield (
                json.dumps({
                    "citation": s["id"],
                    "title": s["title"],
                    "year": s["year"],
                    "url": s["url"],
                    "snippets": s["snippets"]
                }, ensure_ascii=False) + "\n"
            ).encode("utf-8")
    
    return StreamingResponse(gen(), media_type="application/jsonl")

