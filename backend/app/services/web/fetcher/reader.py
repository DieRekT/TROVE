"""Content extraction from web pages using trafilatura and readability."""

import logging
from typing import Optional
import httpx
from urllib.parse import urlparse

from ....models.web_search import ExtractedContent

logger = logging.getLogger(__name__)

# Try to import trafilatura (primary)
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not available, will use fallback")

# Try to import readability (fallback)
try:
    from readability import Document
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False
    logger.warning("readability-lxml not available, will use snippet only")


def fetch_and_extract(url: str, timeout: int = 20) -> Optional[ExtractedContent]:
    """
    Fetch and extract main content from a web page.
    
    Primary: trafilatura
    Fallback: readability-lxml
    Final fallback: return None (use snippet)
    
    Returns ExtractedContent or None if extraction fails.
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://example.com/bot)",
            })
            response.raise_for_status()
            
            html = response.text
            
            # Try trafilatura first
            if TRAFILATURA_AVAILABLE:
                try:
                    extracted = trafilatura.extract(
                        html,
                        include_comments=False,
                        include_tables=False,
                        include_images=False,
                        include_links=False,
                    )
                    if extracted:
                        # Get title
                        title = trafilatura.extract_metadata(html).get("title", "") or urlparse(url).path
                        return ExtractedContent(
                            title=title[:200],
                            text=extracted.strip(),
                            clean_html=None,
                            extraction_method="trafilatura",
                        )
                except Exception as e:
                    logger.debug(f"Trafilatura extraction failed for {url}: {e}")
            
            # Fallback to readability
            if READABILITY_AVAILABLE:
                try:
                    doc = Document(html)
                    title = doc.title() or urlparse(url).path
                    content = doc.summary()
                    # Strip HTML tags for text
                    import re
                    text = re.sub(r"<[^>]+>", "", content).strip()
                    if text:
                        return ExtractedContent(
                            title=title[:200],
                            text=text,
                            clean_html=content,
                            extraction_method="readability",
                        )
                except Exception as e:
                    logger.debug(f"Readability extraction failed for {url}: {e}")
            
            # Final fallback: return None (caller should use snippet)
            logger.debug(f"Could not extract content from {url}, using snippet")
            return None
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} for {url}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None

