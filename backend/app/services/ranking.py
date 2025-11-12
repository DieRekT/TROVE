from __future__ import annotations
import math, re
from typing import List, Optional

WS = re.compile(r'\s+')

def _norm(s: Optional[str]) -> str:
    return WS.sub(' ', (s or '')).strip().lower()

def title_overlap(title: str, terms: List[str]) -> float:
    t = _norm(title)
    if not t: return 0.0
    hits = sum(1 for term in terms if term in t)
    return hits / max(1, len(terms))

def date_proximity(year: Optional[int], y_from: Optional[int], y_to: Optional[int]) -> float:
    if not year or not y_from or not y_to: return 0.5
    mid = (y_from + y_to) / 2
    return 1.0 / (1.0 + abs(year - mid) / max(1.0, (y_to - y_from)/2 or 1.0))

def bm25_to_score(bm25_value: float) -> float:
    """
    Map SQLite FTS5 bm25() score to 0-1 relevance score.
    
    In FTS5, bm25() returns negative values where:
    - More negative (lower) = higher relevance
    - Less negative (higher) = lower relevance
    
    We convert to 0-1 where 1.0 = most relevant.
    Formula: score = 1.0 - (1.0 / (1.0 + abs(bm25_value)))
    
    Examples:
    - bm25=-10 (very relevant) → score ≈ 0.91
    - bm25=-5 (relevant) → score ≈ 0.83
    - bm25=-1 (less relevant) → score ≈ 0.5
    """
    # Handle non-negative bm25 (shouldn't happen in FTS5, but be defensive)
    if bm25_value >= 0:
        return 0.0
    # More negative bm25 = higher relevance = higher score
    # Use: 1.0 - (1.0 / (1.0 + abs(bm25))) so abs(bm25)=10 → 0.91, abs(bm25)=1 → 0.5
    return 1.0 - (1.0 / (1.0 + abs(bm25_value)))

def blend(bm25: float, title_boost: float, date_boost: float, nsw_bonus: float=0.0) -> float:
    # weighted sum → [0..1.7] approx; clamp 0..1
    raw = 0.6*bm25 + 0.25*title_boost + 0.15*date_boost + nsw_bonus
    return max(0.0, min(1.0, raw))
