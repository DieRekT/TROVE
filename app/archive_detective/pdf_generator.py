from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from .config import DOCS_DIR, OUTPUTS_DIR


def _doc(path: Path) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=48
    )


def create_brief_pdf() -> str:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "brief_template.pdf"
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("<b>Brief Template — Archive Detective</b>", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Created: {date.today().strftime('%d %b %Y')}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))
    bullets = [
        "Subject Property — fill in address, legal, parish/county.",
        "Capture Parish (1939, 1968) and Town maps (Ashby) from HLRV.",
        "Read marginal notes for Volume/Folio and Crown Plans.",
        "Open Old-Form Registers; extract owner/dealings.",
        "Locate DP 586103 (image or citation) and Crown Plans.",
        "Enrich with Trove (sales, Reserve AR 55640 context).",
    ]
    story.append(Paragraph("<b>Instructions</b>", styles["Heading2"]))
    story.append(
        ListFlowable([ListItem(Paragraph(b, styles["Normal"])) for b in bullets], bulletType="1")
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("<b>Evidence Log</b>", styles["Heading2"]))
    story.append(Paragraph("Date | Source | Description | Citation/Link | Notes", styles["Code"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("<b>Owner / Title Timeline</b>", styles["Heading2"]))
    story.append(
        Paragraph(
            "Date From | Date To | Owner | Role | Volume/Folio | Dealing | Source | URL | Notes",
            styles["Code"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("<b>Map & Plan Checklist</b>", styles["Heading2"]))
    for line in [
        "Parish of Ashby — 1939 — viewer URL / image ID: __________",
        "Parish of Ashby — 1968 — viewer URL / image ID: __________",
        "Town/Village of Ashby — viewer URL / image ID: __________",
        "DP 586103 — image ID or order reference: ________________",
        "Crown Plan(s) referenced — IDs: _________________________",
    ]:
        story.append(Paragraph("• " + line, styles["Normal"]))
    _doc(out).build(story)
    return str(out)


def create_placeholder_report() -> str:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / "report.pdf"
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>Archive Detective — Placeholder Report</b>", styles["Title"]),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "This is a placeholder report. Fill with timeline and citations after harvest.",
            styles["Normal"],
        ),
    ]
    _doc(out).build(story)
    return str(out)
