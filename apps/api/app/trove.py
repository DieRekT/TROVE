import os
import re

import requests

from .text_clean import html_to_text

TROVE_BASE = "https://api.trove.nla.gov.au/v3"


def _key():
    k = os.getenv("TROVE_API_KEY")
    if not k:
        raise RuntimeError("Missing TROVE_API_KEY")
    return k


def parse_article_id(s: str) -> str:
    m = re.search(r'/article/(\d+)', s)
    if m: return m.group(1)
    m = re.search(r'nla\.news-article(\d+)', s)
    if m: return m.group(1)
    if re.fullmatch(r'\d+', s): return s
    raise ValueError(f"Cannot extract article id from: {s}")


def trove_search(q: str, n=20, date_from=None, date_to=None, state=None):
    params = dict(
        category="newspaper",
        q=q,
        n=n,
        encoding="json",
    )
    if date_from: params["l-decade"] = ""  # we can refine later; keep simple
    # (Trove v3 supports richer filters; MVP sends plain query)
    url = f"{TROVE_BASE}/result"
    headers = {"X-API-KEY": _key(), "Accept": "application/json"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    # Extract minimal cards
    items = []
    for zone in data.get("category", []):
        for rec in zone.get("records", {}).get("article", []):
            items.append({
                "id": rec.get("id"),
                "title": rec.get("title", {}).get("title"),
                "date": rec.get("date"),
                "page": rec.get("page"),
                "snippet": rec.get("snippet"),
                "troveUrl": rec.get("troveUrl"),
            })
    return items


def trove_article(aid: str):
    url = f"{TROVE_BASE}/newspaper/{aid}"
    params = dict(encoding="json", include="articletext")
    headers = {"X-API-KEY": _key(), "Accept": "application/json"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    if r.status_code == 401:
        raise RuntimeError("Invalid Trove key")
    r.raise_for_status()
    data = r.json()
    text = html_to_text(data.get("articleText") or "")
    return {
        "id": data.get("id"),
        "heading": data.get("heading"),
        "title": data.get("title", {}).get("title"),
        "date": data.get("date"),
        "page": data.get("page"),
        "troveUrl": data.get("troveUrl"),
        "text": text
    }

