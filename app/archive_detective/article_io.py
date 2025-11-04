from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import get_settings


def extract_article_id_from_url(url_or_id: str) -> str | None:
    """
    Extract article ID from Trove URL or return as-is if already an ID.
    
    Handles formats like:
    - https://nla.gov.au/nla.news-article184199164?searchTerm=...
    - nla.news-article184199164
    - 184199164
    - Full URLs with query parameters
    """
    if not url_or_id:
        return None
    
    # If it's already just a number, return it
    if url_or_id.strip().isdigit():
        return url_or_id.strip()
    
    # Try to extract from nla.news-article pattern
    # Pattern: nla.news-article<digits>
    match = re.search(r'nla\.news-article(\d{6,})', url_or_id)
    if match:
        return match.group(1)
    
    # Try to extract any sequence of 6+ digits (typical article ID length)
    match = re.search(r'(\d{6,})', url_or_id)
    if match:
        return match.group(1)
    
    # If no pattern found, return None
    return None


async def fetch_item_text(item_id: str, trove_url: str | None = None) -> dict[str, Any]:
    """
    Best-effort fetch of article text. Works well for newspapers/gazettes.
    Falls back to title+snippet when fulltext not available.
    
    Args:
        item_id: Article ID (numeric or nla.news-article format)
        trove_url: Full Trove URL if available (preferred for fetching)
    """
    settings = get_settings()
    if not settings.trove_api_key:
        return {"ok": False, "error": "Missing TROVE_API_KEY"}

    headers = {"X-API-KEY": settings.trove_api_key}
    
    # Try multiple strategies to fetch the article
    strategies = []
    
    # Strategy 1: If we have a full Trove URL, try to extract and use it
    if trove_url:
        # Extract ID from URL if it's a newspaper article URL
        url_id = extract_article_id_from_url(trove_url)
        if url_id:
            strategies.append(("id", url_id))
        # Also try the full URL as identifier
        if "nla.news-article" in trove_url or "nla.gov.au" in trove_url:
            strategies.append(("url", trove_url))
    
    # Strategy 2: Try the provided ID directly
    strategies.append(("id", item_id))
    
    # Strategy 3: Try nla.news-article format if ID is numeric
    if item_id.isdigit():
        strategies.append(("id", f"nla.news-article{item_id}"))
    
    # Strategy 4: Extract numeric ID from nla.news-article format
    if "nla.news-article" in item_id:
        extracted = extract_article_id_from_url(item_id)
        if extracted and extracted != item_id:
            strategies.append(("id", extracted))

    # Try each strategy
    last_error = None
    for strategy_type, identifier in strategies:
        try:
            if strategy_type == "url":
                # Use full URL - parse it to get the article endpoint
                # Trove URLs like: https://nla.gov.au/nla.news-article123456789
                if "nla.news-article" in identifier:
                    article_id = extract_article_id_from_url(identifier)
                    if article_id:
                        params = {"id": article_id, "encoding": "json", "include": "articleText,workText,fulltext"}
                    else:
                        continue
                else:
                    # Try to use URL as-is (might work for some endpoints)
                    params = {"url": identifier, "encoding": "json", "include": "articleText,workText,fulltext"}
            else:
                # Use ID
                params = {"id": identifier, "encoding": "json", "include": "articleText,workText,fulltext"}
            
            url = f"{settings.trove_base_url}/record"
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(url, params=params, headers=headers)
                r.raise_for_status()
                up = r.json()
                # If we got here, the fetch worked - break out of loop
                break
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 404:
                # Try next strategy
                continue
            # For other HTTP errors, try next strategy but remember this error
            continue
        except httpx.RequestError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue
    else:
        # All strategies failed
        if isinstance(last_error, httpx.HTTPStatusError):
            if last_error.response.status_code == 404:
                return {"ok": False, "error": "Article not found or full text not available. This article may only have a snippet available."}
            return {"ok": False, "error": f"Trove API error: {last_error.response.status_code}"}
        elif isinstance(last_error, httpx.RequestError):
            return {"ok": False, "error": f"Network error: {str(last_error)}"}
        else:
            return {"ok": False, "error": f"Unable to fetch article. Tried multiple strategies but all failed."}

    # Try pull common fields
    title = ""
    date = ""
    url = ""
    text = ""
    snippet = ""

    # generic hunt
    def find_first(d: Any, keys: list[str]) -> str:
        if isinstance(d, dict):
            for k in keys:
                if k in d and isinstance(d[k], str) and d[k].strip():
                    return d[k]
            for v in d.values():
                s = find_first(v, keys)
                if s:
                    return s
        elif isinstance(d, list):
            for v in d:
                s = find_first(v, keys)
                if s:
                    return s
        return ""

    title = find_first(up, ["title", "heading", "headingTitle"])
    date = find_first(up, ["date", "issued", "publicationDate", "issuedTo"])
    url = find_first(up, ["troveUrl", "identifier", "url"])
    text = find_first(up, ["articleText", "workText", "fulltext", "text"])
    snippet = find_first(up, ["snippet", "summary", "abstract"])

    # sanitize
    if not text:
        text = snippet or ""
    # strip HTML tags if present
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()

    # Try to extract image URL from the response - multiple strategies
    image_url = find_first(up, ["imageUrl", "image", "thumbnail", "fulltextUrl", "identifier.value"])
    
    # Strategy 1: Check identifiers for image links
    if not image_url:
        identifiers = up.get("identifier") or []
        if isinstance(identifiers, dict):
            identifiers = [identifiers]
        if isinstance(identifiers, list):
            for ident in identifiers:
                if isinstance(ident, dict):
                    linktype = ident.get("linktype") or ident.get("@linktype", "")
                    value = ident.get("value") or ident.get("#text") or ident.get("id")
                    if value and linktype in ("viewcopy", "fulltext", "thumbnail"):
                        image_url = value
                        break
    
    # Strategy 2: Construct from Trove URL patterns
    if not image_url and url:
        if "nla.gov.au" in url or "trove.nla.gov.au" in url:
            # Extract article ID from various URL formats
            article_id = extract_article_id_from_url(url)
            
            if article_id:
                # Newspaper article - use article ID for best image URL
                image_url = f"https://trove.nla.gov.au/newspaper/article/{article_id}/image?hei=1200"
            elif "/newspaper/article/" in url:
                # Try to extract from URL path
                match = re.search(r'/newspaper/article/(\d+)', url)
                if match:
                    article_id = match.group(1)
                    image_url = f"https://trove.nla.gov.au/newspaper/article/{article_id}/image?hei=1200"
                else:
                    # Fallback: append /image to URL
                    image_url = f"{url}/image?hei=1200"
            elif "/nla.news-article" in url:
                # Extract article ID from nla.news-article format
                match = re.search(r'nla\.news-article(\d+)', url)
                if match:
                    article_id = match.group(1)
                    image_url = f"https://trove.nla.gov.au/newspaper/article/{article_id}/image?hei=1200"
                else:
                    image_url = f"{url}/image?hei=1200"
            elif "/nla.obj-" in url:
                # Object-based URL - try image endpoint
                image_url = f"{url}/image?hei=1200"
            else:
                # Generic Trove URL - try image endpoint
                image_url = f"{url}/image?hei=1200"
    
    # Strategy 3: Try to extract from work/contributor records
    if not image_url:
        work = up.get("work") or []
        if isinstance(work, dict):
            work = [work]
        for w in work:
            if isinstance(w, dict):
                w_image = find_first(w, ["imageUrl", "thumbnail", "identifier.value"])
                if w_image:
                    image_url = w_image
                    break
    
    return {
        "ok": True,
        "id": item_id,
        "title": title or "Untitled",
        "date": date,
        "url": url,
        "text": text,
        "image_url": image_url,
        "source": find_first(up, ["source", "publisher", "contributor", "newspaper"]),
    }
