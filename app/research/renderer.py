"""Markdown report renderer for research findings."""

from datetime import datetime
from typing import List

from app.research.schemas import Evidence, Findings


def render_markdown(findings: Findings, evidence: List[Evidence]) -> str:
    """
    Render a comprehensive Markdown report from findings and evidence.

    Includes title, overview, key points, evidence table, limitations,
    next questions, and appendices (JSONL path, CSV bibliography).
    """
    lines = []

    # Title
    lines.append("# Research Findings Report")
    lines.append("")
    lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append(findings.overview)
    lines.append("")

    # Key Points
    lines.append("## Key Points")
    lines.append("")
    for point in findings.key_points:
        lines.append(f"- {point}")
    lines.append("")

    # Evidence Table
    lines.append("## Evidence")
    lines.append("")
    lines.append("| Title | Source | Date | URL |")
    lines.append("|-------|--------|------|-----|")
    for ev in evidence[:50]:  # Limit table size
        title = ev.title.replace("|", "\\|")[:60]
        source = ev.source
        date = ev.published_at or "N/A"
        url = ev.url[:80] if ev.url else "N/A"
        lines.append(f"| {title} | {source} | {date} | {url} |")
    lines.append("")

    # Limitations
    if findings.limitations:
        lines.append("## Limitations")
        lines.append("")
        for limitation in findings.limitations:
            lines.append(f"- {limitation}")
        lines.append("")

    # Next Questions
    if findings.next_questions:
        lines.append("## Suggested Next Questions")
        lines.append("")
        for question in findings.next_questions:
            lines.append(f"- {question}")
        lines.append("")

    # Citations
    lines.append("## Citations")
    lines.append("")
    for i, citation in enumerate(findings.citations, 1):
        lines.append(f"{i}. **{citation.title}**")
        if citation.url:
            lines.append(f"   - URL: {citation.url}")
        lines.append(f"   - Source: {citation.source}")
        lines.append("")

    # Appendices
    lines.append("---")
    lines.append("## Appendices")
    lines.append("")
    lines.append("### Evidence Data")
    lines.append("")
    lines.append("Full evidence data is available in JSONL format in the `evidence.jsonl` file.")
    lines.append("")
    lines.append("### Bibliography (CSV)")
    lines.append("")
    lines.append("Title,URL,Source,Date")
    for ev in evidence:
        title = ev.title.replace('"', '""')
        url = ev.url.replace('"', '""')
        date = ev.published_at or ""
        lines.append(f'"{title}","{url}",{ev.source},"{date}"')
    lines.append("")

    return "\n".join(lines)

