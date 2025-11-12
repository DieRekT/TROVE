from __future__ import annotations
from typing import Optional

NSW_TOKENS = {"nsw","clarence","maclean","grafton","yamba","iluka","ashby","harwood","lower clarence","clarence river"}

def infer_state_from_query(q: str) -> Optional[str]:
    ql = (q or "").lower()
    return "New South Wales" if any(tok in ql for tok in NSW_TOKENS) else None

def nsw_bonus_for_text(t: str) -> float:
    t = (t or "").lower()
    if any(tok in t for tok in ("clarence","maclean","grafton","yamba","iluka","ashby","nsw")):
        return 0.05
    return 0.0
