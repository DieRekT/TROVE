from __future__ import annotations
import re
from typing import List

SPLIT = re.compile(r'(?<=[.!?])\s+')
WS = re.compile(r'\s+')

def _norm(s: str) -> str:
    return WS.sub(' ', (s or '')).strip().lower()

def best_sentences(text: str, terms: List[str], k: int = 2, max_len: int = 240) -> List[str]:
    if not text: return []
    sents = SPLIT.split(WS.sub(' ', text).strip())
    scored = []
    for s in sents:
        t = _norm(s)
        score = sum(1 for term in terms if term in t)
        if score > 0:
            scored.append((score, s.strip()))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    out = []
    seen = set()
    for _, s in scored:
        q = s if len(s) <= max_len else s[:max_len] + "…"
        if q not in seen:
            out.append(q); seen.add(q)
        if len(out) >= k: break
    return out
