#!/usr/bin/env python3
"""Standalone batch research test server - avoids import issues."""
import os
import sys
import asyncio
import json
import time
import uuid
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

# Add backend to path for db and services
sys.path.insert(0, str(Path(__file__).parent))

# Import only what we need directly
from app.db import get_conn, upsert_source
from app.services.trove_batch import ingest_trove, sentence_quotes
from app.services.trove_client import TroveClient

app = FastAPI(title="Batch Research API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class StartJob(BaseModel):
    query: str
    years_from: Optional[int] = None
    years_to: Optional[int] = None
    max_pages: int = 10
    page_size: int = 100
    max_sources_for_report: int = 20

def _terms(q: str) -> List[str]:
    """Extract search terms from query."""
    return [w for w in re.split(r'[^a-z0-9]+', q.lower()) if w and len(w) > 2]

@app.post("/api/research/start-batch")
async def start_batch(req: StartJob):
    """Start a background batch ingestion job."""
    job_id = str(uuid.uuid4())
    now = time.time()
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs(id,query,years_from,years_to,max_pages,status,progress,created_at,updated_at) VALUES(?,?,?,?,?,'queued',0,?,?)",
            (job_id, req.query, req.years_from, req.years_to, req.max_pages, now, now)
        )
    
    async def worker():
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                    (time.time(), job_id)
                )
            
            retrieved, stored = await ingest_trove(
                req.query,
                req.years_from,
                req.years_to,
                req.max_pages,
                req.page_size
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

@app.get("/api/research/job/{job_id}")
def job_status(job_id: str):
    """Get job status."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return dict(row)

@app.get("/api/research/job/{job_id}/report")
def job_report(job_id: str, max_sources: int = 20):
    """Build a verified report from indexed evidence."""
    with get_conn() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "job not found")
        if job["status"] != "done":
            raise HTTPException(409, "job not complete")
        
        q = job["query"]
        terms = _terms(q)
        query_terms = " OR ".join(terms)
        rows = conn.execute("""
            SELECT s.id, s.title, s.year, s.url, s.text
            FROM sources_fts f
            JOIN sources s ON s.id = f.id
            WHERE f MATCH ?
            LIMIT ?
        """, (query_terms, max_sources)).fetchall()
        
        sources = []
        for r in rows:
            quotes = sentence_quotes(r["text"] or "", terms, max_out=2)
            sources.append({
                "id": r["id"],
                "title": r["title"],
                "year": r["year"],
                "url": r["url"],
                "snippets": quotes,
                "relevance": 1.0
            })
        
        if not sources:
            raise HTTPException(422, "No evidence found in index for this job.")
        
        findings = []
        timeline = []
        for s in sources[:5]:
            findings.append({
                "title": s["title"] or "Untitled",
                "insight": s["title"] or "",
                "evidence": s["snippets"],
                "citations": [s["id"]],
                "confidence": 0.65
            })
            if s["year"]:
                timeline.append({
                    "date": f"{s['year']:04d}-01-01",
                    "event": (s["title"] or "")[:120],
                    "citations": [s["id"]]
                })
        
        resp = {
            "query": q,
            "executive_summary": f"This report compiles Trove evidence for '{q}'.",
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

@app.get("/api/research/job/{job_id}/markdown", response_class=PlainTextResponse)
def job_markdown(job_id: str, max_sources: int = 20):
    """Export report as Markdown."""
    r = job_report(job_id, max_sources=max_sources).body
    data = json.loads(r)
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

@app.get("/api/research/job/{job_id}/evidence")
def job_evidence(job_id: str, max_sources: int = 20):
    """Export evidence as JSONL."""
    r = job_report(job_id, max_sources=max_sources).body
    data = json.loads(r)
    def gen():
        for s in data.get("sources", []):
            yield (json.dumps({
                "citation": s["id"],
                "title": s["title"],
                "year": s["year"],
                "url": s["url"],
                "snippets": s["snippets"]
            }, ensure_ascii=False) + "\n").encode("utf-8")
    return StreamingResponse(gen(), media_type="application/jsonl")

@app.get("/")
async def root():
    return {
        "message": "Batch Research API - Test Server",
        "docs": "/docs",
        "endpoints": [
            "POST /api/research/start-batch - Start a batch job",
            "GET /api/research/job/{job_id} - Check job status",
            "GET /api/research/job/{job_id}/report - Get verified report",
            "GET /api/research/job/{job_id}/markdown - Export as Markdown",
            "GET /api/research/job/{job_id}/evidence - Export as JSONL",
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    print(f"🚀 Starting Batch Research API on http://127.0.0.1:{port}")
    print(f"📚 API Docs: http://127.0.0.1:{port}/docs")
    uvicorn.run("test_batch_standalone:app", host="127.0.0.1", port=port, reload=True)

