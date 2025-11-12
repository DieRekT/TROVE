from __future__ import annotations
from time import time
from typing import Any, Tuple, Optional


class TTLCache:
    def __init__(self, ttl_sec: int = 300):
        self.ttl = ttl_sec
        self.store: dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        v = self.store.get(key)
        if not v:
            return None
        ts, data = v
        if time() - ts > self.ttl:
            self.store.pop(key, None)
            return None
        return data

    def set(self, key: str, val: Any) -> None:
        self.store[key] = (time(), val)

