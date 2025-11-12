from __future__ import annotations

import httpx
import re
from typing import Optional


def _clean(txt: str) -> str:
    txt = re.sub(r'\s+', ' ', (txt or '')).strip()
    return txt


async def fetch_url(url: str, timeout: float = 20.0) -> Optional[str]:
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "ArchiveDetective/1.0"}) as c:
        r = await c.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text


def trafilatura_extract(html: str) -> Optional[str]:
    try:
        import trafilatura
        txt = trafilatura.extract(html, include_comments=False, include_tables=False)
        return _clean(txt) if txt else None
    except Exception:
        return None


def readability_extract(html: str) -> Optional[str]:
    try:
        from readability import Document
        from lxml import html as lhtml
        doc = Document(html)
        body = doc.summary(html_partial=True)
        tree = lhtml.fromstring(body)
        text = ' '.join(tree.xpath('string()').split())
        return _clean(text) or None
    except Exception:
        return None

