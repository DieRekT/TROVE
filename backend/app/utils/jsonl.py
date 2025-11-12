from __future__ import annotations
from typing import Iterable, Dict, Any, Generator
import json


def to_jsonl(items: Iterable[Dict[str, Any]]) -> Generator[str, None, None]:
    for it in items:
        yield json.dumps(it, ensure_ascii=False) + "\n"

