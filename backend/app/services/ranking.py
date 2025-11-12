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
    # SQLite FTS5 bm25: smaller is better; normalize to (0,1], monotonic
    return 1.0 / (1.0 + max(0.0, bm25_value))

def blend(bm25: float, title_boost: float, date_boost: float, nsw_bonus: float=0.0) -> float:
    # weighted sum → [0..1.7] approx; clamp 0..1
    raw = 0.6*bm25 + 0.25*title_boost + 0.15*date_boost + nsw_bonus
    return max(0.0, min(1.0, raw))
