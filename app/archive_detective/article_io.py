from __future__ import annotations

import re
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _clean_scraped_text(text: str) -> str:
    """
    Clean scraped HTML text, preserving paragraph breaks.
    
    Args:
        text: Raw text (may contain HTML)
        
    Returns:
        Cleaned text with preserved paragraph breaks
    """
    if not text:
        return ""
    
    # First, convert common HTML line breaks to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "\n", text, flags=re.IGNORECASE)
    
    # Remove other HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    
    # Normalize whitespace but preserve paragraph breaks
    # Replace multiple spaces/tabs with single space (but keep newlines)
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs to single space
    # Replace 3+ newlines with double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    # Final cleanup: remove empty lines at start/end
    text = text.strip()
    
    return text


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
    up = None
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
                # Use ID - use /record endpoint directly (best for fetching specific articles)
                params = {"id": identifier, "encoding": "json", "include": "articleText,workText,fulltext,links"}
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
        # All API strategies failed - try scraping before giving up
        # If we have a URL (from trove_url parameter), try scraping as a fallback
        scrape_url = trove_url
        # If no URL provided, try to construct one from the article ID
        if not scrape_url and item_id:
            # Try to construct Trove URL from article ID
            if item_id.isdigit():
                scrape_url = f"https://nla.gov.au/nla.news-article{item_id}"
            elif "nla.news-article" in item_id:
                article_id = extract_article_id_from_url(item_id)
                if article_id:
                    scrape_url = f"https://nla.gov.au/nla.news-article{article_id}"
        
        if scrape_url:
            try:
                logger.info(f"📄 API fetch failed, attempting to scrape from {scrape_url}")
                scraped_text = await _scrape_article_text(scrape_url)
                if scraped_text and len(scraped_text) > 100:
                    # We got text from scraping, so we can continue with that
                    # Create a minimal response structure
                    up = None  # None indicates scraping was used (API failed)
                    # Extract basic info from URL if possible
                    article_id = extract_article_id_from_url(scrape_url) or item_id
                    # Use scraped text as the text source
                    text = scraped_text
                    snippet = ""  # No snippet from scraping
                    # Try to extract title from scraped text or use default
                    title = scraped_text.split('\n')[0][:100] if scraped_text else "Untitled"
                    date = ""
                    url = scrape_url  # Set url for later processing
                    source = ""
                    # Set flag to indicate scraping was used
                    scraped_successfully = True
                    # Continue processing with scraped text
                    logger.info(f"✅ Scraping succeeded, using scraped text ({len(text)} chars)")
                    # Fall through to text processing below (skip the find_first calls since up is None)
                else:
                    # Scraping also failed or returned insufficient text
                    if isinstance(last_error, httpx.HTTPStatusError):
                        if last_error.response.status_code == 404:
                            return {"ok": False, "error": "Article not found or full text not available. This article may only have a snippet available."}
                        return {"ok": False, "error": f"Trove API error: {last_error.response.status_code}"}
                    elif isinstance(last_error, httpx.RequestError):
                        return {"ok": False, "error": f"Network error: {str(last_error)}"}
                    else:
                        return {"ok": False, "error": f"Unable to fetch article. Tried API and scraping but all failed."}
            except Exception as scrape_err:
                # Scraping failed too, return API error
                logger.debug(f"Scraping also failed: {scrape_err}")
                if isinstance(last_error, httpx.HTTPStatusError):
                    if last_error.response.status_code == 404:
                        return {"ok": False, "error": "Article not found or full text not available. This article may only have a snippet available."}
                    return {"ok": False, "error": f"Trove API error: {last_error.response.status_code}"}
                elif isinstance(last_error, httpx.RequestError):
                    return {"ok": False, "error": f"Network error: {str(last_error)}"}
                else:
                    return {"ok": False, "error": f"Unable to fetch article. Tried API and scraping but all failed."}
        else:
            # No URL to scrape, return API error
            if isinstance(last_error, httpx.HTTPStatusError):
                if last_error.response.status_code == 404:
                    return {"ok": False, "error": "Article not found or full text not available. This article may only have a snippet available."}
                return {"ok": False, "error": f"Trove API error: {last_error.response.status_code}"}
            elif isinstance(last_error, httpx.RequestError):
                return {"ok": False, "error": f"Network error: {str(last_error)}"}
            else:
                return {"ok": False, "error": f"Unable to fetch article. Tried multiple strategies but all failed."}

    # Check if we scraped (indicated by up = None set in scraping fallback)
    # When scraping succeeds, we set up = None and text/title/url directly
    scraped_flag = (up is None)
    
    # Try pull common fields
    # Initialize with empty values (will be set from API or already set from scraping)
    if not scraped_flag:
        # Not scraped - initialize empty (will be filled from API)
        title = ""
        date = ""
        url = ""
        text = ""
        snippet = ""
    else:
        # We scraped - text/title/url are already set in scraping block above
        # Just ensure URL is set if not already
        if not url and trove_url:
            url = trove_url
        if not snippet:
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

    # Only try to extract from API response if we have one (up is not None)
    # If we scraped, skip API extraction entirely (up is None)
    if not scraped_flag and up is not None:
        title = find_first(up, ["title", "heading", "headingTitle"])
        date = find_first(up, ["date", "issued", "publicationDate", "issuedTo"])
        url = find_first(up, ["troveUrl", "identifier", "url"])
        
        # Extract snippet from original response before potentially reassigning up
        # This ensures we don't miss snippet data if it exists at root level but not in nested records
        snippet = find_first(up, ["snippet", "summary", "abstract"])
        
        # Try to find full text - check multiple field names and nested structures
        # First check if response is nested in a "record" key (common Trove API structure)
        original_up = up  # Keep reference to original for consistent data extraction
        if isinstance(up, dict) and "record" in up:
            record_data = up["record"]
            if isinstance(record_data, dict):
                up = record_data
            elif isinstance(record_data, list) and len(record_data) > 0:
                up = record_data[0]
        
        # Try to find full text - check multiple field names and nested structures
        # Priority: articleText > workText > fulltext > text
        text = find_first(up, [
            "articleText", "workText", "fulltext", "text", "fullText",
            "articleText.value", "workText.value", "fulltext.value",
            "text.value", "content", "body", "description"
        ])
        
        # If not found at top level, check in work records (common location for articleText)
        if not text or len(text) < 100:
            work = up.get("work") or []
            if isinstance(work, dict):
                work = [work]
            for w in work:
                if isinstance(w, dict):
                    work_text = find_first(w, [
                        "articleText", "workText", "fulltext", "text", "fullText",
                        "articleText.value", "workText.value", "fulltext.value",
                        "text.value", "content", "body"
                    ])
                    if work_text and len(work_text) > len(text or ""):
                        text = work_text
                    
                    # Also check nested articleText in work
                    if not text or len(text) < 100:
                        # Check if work has an article nested inside
                        work_article = w.get("article") or []
                        if isinstance(work_article, dict):
                            work_article = [work_article]
                        for wa in work_article:
                            if isinstance(wa, dict):
                                wa_text = find_first(wa, ["articleText", "text", "fulltext"])
                                if wa_text and len(wa_text) > len(text or ""):
                                    text = wa_text
        
        # Check in contributor records
        if not text:
            contributor = up.get("contributor") or []
            if isinstance(contributor, dict):
                contributor = [contributor]
            for c in contributor:
                if isinstance(c, dict):
                    contrib_text = find_first(c, [
                        "articleText", "workText", "fulltext", "text", "fullText",
                        "articleText.value", "workText.value", "fulltext.value",
                        "text.value", "content", "body"
                    ])
                    if contrib_text and len(contrib_text) > len(text or ""):
                        text = contrib_text
        
        # Also check for snippet in nested record if not found in original
        # Prefer longer snippet if both exist
        nested_snippet = find_first(up, ["snippet", "summary", "abstract"])
        if nested_snippet and len(nested_snippet) > len(snippet or ""):
            snippet = nested_snippet
    elif not scraped_flag:
        # No API response and no scraping, use trove_url if available
        if not url and trove_url:
            url = trove_url
        snippet = ""

    # If we don't have full text or it's too short, try scraping from the HTML page
    # Scrape if: no text OR text is short (< 500 chars, likely just a snippet)
    # Full articles are usually 500+ characters, so anything shorter is likely incomplete
    should_scrape = url and (not text or len(text) < 500)
    if should_scrape:
        try:
            logger.info(f"📄 Attempting to scrape full text from {url} (API text: {len(text) if text else 0} chars)")
            scraped_text = await _scrape_article_text(url)
            if scraped_text and len(scraped_text) > 100:
                # Use scraped text if it's longer than what we have
                # Full articles should be significantly longer than snippets
                if not text or len(scraped_text) > len(text) * 1.2:  # At least 20% longer
                    old_len = len(text) if text else 0
                    text = scraped_text
                    logger.info(f"✅ Using scraped text ({len(text)} chars, was {old_len} chars) from {url}")
        except Exception as scrape_err:
            # Log but don't fail - scraping is a fallback
            logger.debug(f"Scraping failed for {url}: {scrape_err}")
    
    # Prioritize full text over snippet - only use snippet if we have no text at all
    # or if text is extremely short (likely incomplete)
    if not text or (text and len(text) < 50):
        text = snippet or text or ""
    
    # If we have both text and snippet, prefer the longer one (likely more complete)
    # But only use snippet if it's significantly longer (don't replace good scraped text)
    if snippet and len(snippet) > len(text or "") * 1.5:
        text = snippet
        logger.debug(f"Using snippet ({len(snippet)} chars) over text ({len(text)} chars)")
    
    # strip HTML tags if present, but preserve line breaks
    if text:
        # First, convert common HTML line breaks to newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)
        # Remove other HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Normalize whitespace but preserve paragraph breaks
        text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs to single space
        text = re.sub(r"\n{3,}", "\n\n", text)  # Multiple newlines to double newline
        text = text.strip()

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
        "snippet": snippet,  # Also return snippet for reference
    }


async def _scrape_article_text(url: str) -> str | None:
    """
    Scrape full article text from Trove HTML page.
    Uses trafilatura (primary) or readability-lxml (fallback).
    
    Args:
        url: Trove article URL
        
    Returns:
        Extracted text or None if scraping fails
    """
    if not url:
        return None
    
    # Only try scraping Trove URLs
    if "nla.gov.au" not in url and "trove.nla.gov.au" not in url:
        return None
    
    try:
        # Fetch HTML page
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "ArchiveDetective/1.0"}) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text
        
        # Try trafilatura first (better for news articles)
        try:
            import trafilatura
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_images=False,
                include_links=False,
            )
            if extracted:
                # Clean HTML but preserve paragraph breaks
                text = _clean_scraped_text(extracted)
                if text and len(text) > 100:
                    logger.info(f"✅ Successfully scraped text with trafilatura from {url} ({len(text)} chars)")
                    return text
        except ImportError:
            logger.debug("trafilatura not available, trying readability")
        except Exception as e:
            logger.debug(f"trafilatura extraction failed: {e}")
        
        # Fallback to readability-lxml
        try:
            from readability import Document
            from lxml import html as lhtml
            doc = Document(html)
            body = doc.summary(html_partial=True)
            tree = lhtml.fromstring(body)
            # Extract text preserving structure
            text = tree.text_content() if hasattr(tree, 'text_content') else tree.xpath('string()')
            # Clean HTML but preserve paragraph breaks
            text = _clean_scraped_text(text)
            if text and len(text) > 100:
                logger.info(f"✅ Successfully scraped text with readability from {url} ({len(text)} chars)")
                return text
        except ImportError:
            logger.debug("readability-lxml not available")
        except Exception as e:
            logger.debug(f"readability extraction failed: {e}")
        
        return None
        
    except httpx.TimeoutException:
        logger.debug(f"Timeout scraping {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP {e.response.status_code} when scraping {url}")
        return None
    except Exception as e:
        logger.debug(f"Error scraping {url}: {e}")
        return None
