from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATA_DIR, OUTPUTS_DIR

STATE = DATA_DIR / "reports" / "current.json"
STATE.parent.mkdir(parents=True, exist_ok=True)


def load_report() -> dict[str, Any]:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # If file is corrupted, return empty report
            return {"title": "Archive Detective Report", "items": []}
    return {"title": "Archive Detective Report", "items": []}


def save_report(doc: dict[str, Any]) -> None:
    try:
        STATE.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        # Log error but don't crash - could be permission issue
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to save report: {e}")
        raise


def add_item(item: dict[str, Any]) -> dict[str, Any]:
    doc = load_report()
    doc["items"].append(item)
    save_report(doc)
    return doc


def clear_report() -> None:
    save_report({"title": "Archive Detective Report", "items": []})


def make_pdf(title: str | None = None) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    doc = load_report()
    if title:
        doc["title"] = title
    p = OUTPUTS_DIR / "article_report.pdf"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(p), pagesize=A4)
    W, H = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, H - 2.5 * cm, doc.get("title", "Archive Detective Report"))
    y = H - 3.5 * cm
    c.setFont("Helvetica", 10)
    for i, it in enumerate(doc.get("items", []), start=1):
        fields = [
            f"{i}. {it.get('title', 'Untitled')} ({it.get('date', '')})",
            it.get("url", ""),
            "",
        ]
        for ln in fields:
            c.drawString(2 * cm, y, ln[:120])
            y -= 0.6 * cm
            if y < 3 * cm:
                c.showPage()
                y = H - 3 * cm
                c.setFont("Helvetica", 10)
        # bullets if present
        for b in it.get("bullets") or []:
            c.drawString(2.5 * cm, y, ("- " + b).strip()[:110])
            y -= 0.55 * cm
            if y < 3 * cm:
                c.showPage()
                y = H - 3 * cm
                c.setFont("Helvetica", 10)
        y -= 0.3 * cm
    c.showPage()
    c.save()
    return p
