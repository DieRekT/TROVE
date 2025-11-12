from __future__ import annotations
import logging
from typing import Optional
try:
    import trafilatura  # type: ignore
except Exception:  # pragma: no cover
    trafilatura = None
try:
    from readability import Document  # type: ignore
    import lxml.html  # noqa: F401
except Exception:  # pragma: no cover
    Document = None  # type: ignore

log = logging.getLogger(__name__)


def html_to_text(html: str) -> str:
    html = (html or "").strip()
    if not html:
        return ""
    # 1) Trafilatura (best quality)
    if trafilatura is not None:
        try:
            out = trafilatura.extract(html, include_tables=False, include_comments=False) or ""
            if out.strip():
                return out.strip()
        except Exception as e:  # pragma: no cover
            log.warning("trafilatura failed: %s", e)
    # 2) readability-lxml fallback
    if Document is not None:
        try:
            doc = Document(html)
            # Pull text from the summary HTML
            from lxml import html as LH  # type: ignore
            tree = LH.fromstring(doc.summary())
            text = " ".join(tree.itertext())
            import re
            return re.sub(r"\s+", " ", text).strip()
        except Exception as e:  # pragma: no cover
            log.warning("readability failed: %s", e)
    return ""

