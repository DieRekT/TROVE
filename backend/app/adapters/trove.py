import os
from typing import Any

from httpx import AsyncClient

# ——— Helpers ———


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    # Trove v2/v3 vary; we defensively extract common fields.
    title = raw.get("title") or raw.get("heading") or raw.get("name") or "Untitled"
    date = raw.get("issueDate") or raw.get("date") or raw.get("issued")
    snippet = raw.get("snippet") or raw.get("summary") or raw.get("troveUrl")
    identifier = (
        str(raw.get("id"))
        or raw.get("identifier")
        or raw.get("recordID")
        or (raw.get("work") or {}).get("id")
        or title
    )
    type_ = raw.get("type") or raw.get("category") or raw.get("zone")
    url = raw.get("url") or raw.get("troveUrl") or raw.get("identifier")
    thumb = (raw.get("thumbnail") or raw.get("thumb")) or (raw.get("image") or {}).get("thumbnail")
    return {
        "id": identifier,
        "title": title,
        "snippet": snippet,
        "date": date,
        "type": type_,
        "source": "Trove",
        "url": url,
        "thumbnail": thumb,
    }


_SAMPLE = {
    "total": 3,
    "items": [
        {
            "id": "sample-1",
            "title": "ASHBY. (Daily Examiner, 3 Sep 1918)",
            "snippet": "Mr. Robt. J. Forrester …",
            "date": "1918-09-03",
            "type": "newspaperArticle",
            "troveUrl": "https://trove.nla.gov.au/…",
        },
        {
            "id": "sample-2",
            "title": "Harwood Island – sugar industry photo",
            "snippet": "Historic photo from Clarence River region.",
            "date": "1930-01-01",
            "type": "photograph",
            "troveUrl": "https://trove.nla.gov.au/…",
        },
        {
            "id": "sample-3",
            "title": "Shipping movements – Maclean",
            "snippet": "Notices of departures and arrivals.",
            "date": "1907-05-14",
            "type": "newspaperArticle",
            "troveUrl": "https://trove.nla.gov.au/…",
        },
    ],
}


async def search_trove(client: AsyncClient, q: str, page: int, page_size: int) -> dict[str, Any]:
    if os.getenv("TROVE_MOCK", "false").lower() == "true":
        # deterministic mock for dev
        start = (page - 1) * page_size
        end = start + page_size
        items = _SAMPLE["items"][start:end]
        return {"total": _SAMPLE["total"], "items": [_normalize_item(x) for x in items]}

    base = os.getenv("TROVE_BASE_URL", "https://api.trove.nla.gov.au/v3")
    key = os.getenv("TROVE_API_KEY")
    if not key:
        raise ValueError("TROVE_API_KEY is not set; or enable TROVE_MOCK=true for offline dev")

    # Trove v3 example: /result?category=newspaper&q=term&encoding=json&n=20&s=0
    # We request multiple categories for a general search. Adjust as needed later.
    start = max(0, (page - 1) * page_size)
    url = f"{base}/result"
    params = {
        "q": q,
        "category": "all",
        "encoding": "json",
        "n": str(page_size),
        "s": str(start),
    }

    r = await client.get(url, params=params, headers={"X-API-KEY": key})
    r.raise_for_status()
    data = r.json()

    # Normalize results from possible shapes
    items: list[dict[str, Any]] = []
    total = 0

    # v3 can include a top-level 'total' and 'items' list; fallbacks try known shapes
    if isinstance(data, dict):
        # Try to get total from category buckets
        categories = data.get("category") or []
        if isinstance(categories, dict):
            categories = [categories]
        for cat in categories:
            if isinstance(cat, dict):
                records = cat.get("records", {})
                if isinstance(records, dict):
                    total += int(records.get("total", 0))
                    # Extract items from various containers
                    for container in ("work", "article", "item", "record"):
                        raw_items = records.get(container)
                        if raw_items:
                            if isinstance(raw_items, list):
                                items.extend(raw_items)
                            elif isinstance(raw_items, dict):
                                items.append(raw_items)
                elif isinstance(records, list):
                    items.extend(records)

        # Fallback to direct items if available
        if not items:
            raw_items = data.get("items") or data.get("results") or data.get("work") or []
            items = raw_items if isinstance(raw_items, list) else [raw_items] if raw_items else []
            total = data.get("total", len(items))

    normalized_items = []
    for x in items:
        try:
            normalized_items.append(_normalize_item(x))
        except Exception:
            # Best-effort normalization; skip bad items, never break search
            continue

    return {"total": total or len(normalized_items), "items": normalized_items}
