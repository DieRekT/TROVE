from __future__ import annotations
from ..models.deep_research import DeepResearchResponse


def render_markdown(r: DeepResearchResponse) -> str:
    md = []
    md.append(
        f"# Deep Research Report\n\n**Query:** {r.query}\n\n**Generated:** {r.generated_at}\n"
    )
    md.append("## Executive Summary\n" + r.executive_summary + "\n")
    md.append("## Key Findings")
    for i, f in enumerate(r.key_findings, 1):
        md.append(f"### {i}. {f.title}\n{f.insight}\n")
        if f.evidence:
            md.append("**Evidence:**")
            for q in f.evidence:
                md.append(f"> {q}")
        if f.citations:
            md.append("**Citations:** " + ", ".join(f.citations))
        md.append("")

    if r.timeline:
        md.append("## Timeline")
        for t in r.timeline:
            md.append(f"- {t.date}: {t.event} ({', '.join(t.citations)})")

    if r.entities:
        md.append("## Entities")
        for k, vs in r.entities.items():
            if vs:
                md.append(f"- **{k.title()}**: " + ", ".join(vs))

    if r.sources:
        md.append("## Sources")
        for s in r.sources:
            line = f"- {s.title}"
            if s.url:
                line += f" — {s.url}"
            if s.year:
                line += f" — {s.year}"
            line += f" — rel={s.relevance:.2f}"
            md.append(line)

    md.append("## Methodology\n- " + "\n- ".join(r.methodology))
    md.append("## Limitations\n- " + "\n- ".join(r.limitations))
    md.append("## Next Questions\n- " + "\n- ".join(r.next_questions))

    return "\n".join(md)

