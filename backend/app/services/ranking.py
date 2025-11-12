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

def bm25_to_score(bm25_value: float, min_bm25: float | None = None, max_bm25: float | None = None) -> float:
    """
    Map SQLite FTS5 bm25() score to 0-1 relevance score using min-max normalization.
    
    In FTS5, bm25() returns negative values where:
    - More negative (lower) = higher relevance
    - Less negative (higher) = lower relevance
    
    When min_bm25 and max_bm25 are provided, uses min-max normalization:
    score = (max_bm25 - bm25_value) / (max_bm25 - min_bm25 + 1e-9)
    
    This ensures:
    - Most relevant (lowest bm25) → score = 1.0
    - Least relevant (highest bm25) → score = 0.0
    - All scores in between are linearly interpolated
    
    If min/max not provided, falls back to a simple normalization:
    score = 1.0 - (1.0 / (1.0 + abs(bm25_value)))
    """
    # Handle non-negative bm25 (shouldn't happen in FTS5, but be defensive)
    if bm25_value >= 0:
        return 0.0
    
    # Use min-max normalization if min/max provided
    if min_bm25 is not None and max_bm25 is not None:
        # Prevent division by zero
        denominator = max_bm25 - min_bm25
        if denominator < 1e-9:
            # All values are the same, return 1.0 for all (they're all equally relevant)
            return 1.0
        # Normalize: (max - value) / (max - min) so lower bm25 → higher score
        score = (max_bm25 - bm25_value) / denominator
        return max(0.0, min(1.0, score))
    
    # Fallback: simple normalization when min/max not available
    return 1.0 - (1.0 / (1.0 + abs(bm25_value)))


def normalize_bm25_scores(bm25_values: List[float]) -> List[float]:
    """
    Normalize a list of BM25 scores to 0-1 range using min-max normalization.
    
    Returns normalized scores in the same order as input.
    """
    if not bm25_values:
        return []
    
    # Filter out invalid values (non-negative)
    valid_values = [v for v in bm25_values if v < 0]
    if not valid_values:
        # All invalid, return zeros
        return [0.0] * len(bm25_values)
    
    min_bm25 = min(valid_values)
    max_bm25 = max(valid_values)
    
    # Normalize each value
    normalized = []
    for v in bm25_values:
        if v >= 0:
            normalized.append(0.0)
        else:
            score = bm25_to_score(v, min_bm25, max_bm25)
            normalized.append(score)
    
    return normalized

def blend(bm25: float, title_boost: float, date_boost: float, nsw_bonus: float=0.0) -> float:
    # weighted sum → [0..1.7] approx; clamp 0..1
    raw = 0.6*bm25 + 0.25*title_boost + 0.15*date_boost + nsw_bonus
    return max(0.0, min(1.0, raw))
