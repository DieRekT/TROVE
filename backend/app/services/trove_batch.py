from __future__ import annotations
from typing import Tuple
import asyncio
import re
import math
import time
from typing import Optional, List, Dict, Any, Tuple
from .trove_client import TroveClient
from ..db import get_conn, upsert_source


SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')


def sentence_quotes(text: str, terms: List[str], max_out: int = 2) -> list[str]:
    """Extract relevant sentences containing query terms."""
    if not text:
        return []
    sents = SENT_SPLIT.split(re.sub(r'\s+', ' ', text).strip())
    scored = []
    for s in sents:
        t = s.lower()
        score = sum(1 for term in terms if term in t)
        if score:
            scored.append((score, s.strip()))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    out, seen = [], set()
    for _, s in scored:
        if s in seen:
            continue
        out.append(s[:240] + ('…' if len(s) > 240 else ''))
        seen.add(s)
        if len(out) >= max_out:
            break
    return out


async def ingest_trove(
    query: str,
    yfrom: Optional[int],
    yto: Optional[int],
    max_pages: int = 20,
    page_size: int = 100,
    job_id: str | None = None,
    state: str | None = None) -> Tuple[int, int]:
    """
    Pull paged Trove results and store in SQLite. Returns (retrieved, stored).
    Trove v3: supports 'n' (page_size) and 's' (offset). We step offsets until max_pages or no more hits.
    Updates job progress after each page if job_id is provided.
    """
    client = TroveClient()
    retrieved = stored = 0
    next_start = None  # Token-based pagination for Trove API v3
    
    for page in range(max_pages):
        payload = await client.search(
            q=query,
            n=page_size,
            year_from=yfrom,
            year_to=yto,
            offset=next_start,  # Pass token instead of numeric offset
            state=state
        )
        hits = client.extract_hits(payload)
        if not hits:
            # mark near-complete when no more hits
            if job_id:
                with get_conn() as conn:
                    conn.execute("UPDATE jobs SET progress=?, updated_at=? WHERE id=?",
                                 (min(0.99, (page)/(max_pages)), time.time(), job_id))
            break
        
        # Extract nextStart token for next page
        next_start = None
        for cat in payload.get("category", []):
            recs = cat.get("records", {})
            next_start = recs.get("nextStart")
            if next_start:
                break
        
        retrieved += len(hits)
        
        # Write to database
        with get_conn() as conn:
            for rec in hits:
                sid = str(
                    rec.get("id") or
                    rec.get("workId") or
                    rec.get("articleId") or
                    rec.get("recordId") or
                    "UNKNOWN"
                )
                sid = f"TROVE:{sid}"
                title = rec.get("heading") or rec.get("title") or "Untitled"
                url = client.article_url(rec)
                year = client.year_from_any(rec)
                text = ((rec.get("articleText") or "") + " " + (rec.get("snippet") or "")).strip()
                
                upsert_source(conn, sid, str(title), year, url, text, rec)
                stored += 1
            
            # progress after each page
            if job_id:
                conn.execute("UPDATE jobs SET progress=?, updated_at=? WHERE id=?",
                             (min(0.99, (page+1)/max_pages), time.time(), job_id))
    
    return retrieved, stored

