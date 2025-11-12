from __future__ import annotations
from typing import List, Dict, Any, Optional
from ..services.ranking import bm25_to_score, title_overlap, date_proximity, blend
from ..services.geo import nsw_bonus_for_text
from ..services.quotes import best_sentences


def enrich_sources(sources: List[Dict[str, Any]], query_terms: List[str], y_from: Optional[int], y_to: Optional[int]) -> List[Dict[str, Any]]:
    """Enrich sources with blended relevance scores."""
    out = []
    for s in sources:
        # Get BM25 value (may be in 'rank' or 'bm25' field)
        bm25_raw = s.get("bm25") or s.get("rank", 1.0)
        bm25 = bm25_to_score(float(bm25_raw))
        
        # Title overlap boost
        tb = title_overlap(s.get("title", ""), query_terms)
        
        # Date proximity boost
        dp = date_proximity(s.get("year"), y_from, y_to)
        
        # NSW bonus
        text_for_bonus = " ".join([s.get("title", ""), *(s.get("snippets") or [])])
        nswb = nsw_bonus_for_text(text_for_bonus)
        
        # Blend all factors
        rel = blend(bm25, tb, dp, nswb)
        s["relevance"] = round(rel, 3)
        out.append(s)
    
    # Sort by relevance (highest first)
    out.sort(key=lambda x: x["relevance"], reverse=True)
    return out


def pick_findings(sources: List[Dict[str, Any]], query_terms: List[str]) -> List[Dict[str, Any]]:
    """Extract findings with verbatim quotes from top sources."""
    findings = []
    for s in sources[:5]:
        # Extract best sentences from combined text
        text_for_quotes = " ".join(s.get("snippets") or [])
        if not text_for_quotes:
            text_for_quotes = s.get("text", "") or s.get("title", "")
        
        ev = best_sentences(text_for_quotes, query_terms, k=2)
        
        # Create insight from title and top terms
        title = s.get("title", "Untitled")
        top_terms = [t for t in query_terms if t in title.lower()][:3]
        insight = f"{title}" if not top_terms else f"{title} mentions {', '.join(top_terms)}."
        
        findings.append({
            "title": title,
            "insight": insight,
            "evidence": ev,
            "citations": [s.get("id")],
            "confidence": min(0.9, 0.6 + 0.3 * s.get("relevance", 0.0))
        })
    return findings

