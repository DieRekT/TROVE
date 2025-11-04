from typing import Any


def first_non_empty(*vals: str | None) -> str | None:
    for v in vals:
        if v and str(v).strip():
            return v
    return None


def safe_get(d: dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur
