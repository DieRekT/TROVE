from __future__ import annotations

from .config import OUTPUTS_DIR, ensure_dirs
from .pdf_generator import create_brief_pdf, create_placeholder_report
from .queries import generate_trove_queries_csv


def cmd_generate_queries() -> str:
    ensure_dirs()
    return generate_trove_queries_csv()


def cmd_make_brief() -> str:
    ensure_dirs()
    return create_brief_pdf()


def cmd_harvest_stub() -> str:
    ensure_dirs()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTPUTS_DIR / "owner_timeline.csv"
    if not p.exists():
        p.write_text("date,owner,role,volume_folio,dealing,source,url,notes\n", encoding="utf-8")
    return f"Harvested placeholder to {p}"


def cmd_report() -> str:
    ensure_dirs()
    return create_placeholder_report()
