from __future__ import annotations
import os
from typing import List, Dict, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def exec_summary(query: str, findings: List[Dict[str, Any]], timeline: List[Dict[str, Any]]) -> str:
    """Generate executive summary with citations using OpenAI structured output."""
    if not OPENAI_AVAILABLE:
        # Fallback: simple concatenation
        bullets = []
        for f in findings[:5]:
            cites = ", ".join(f.get("citations", []))
            ev = " ".join(f.get("evidence", [])[:1])
            bullets.append(f"- {f.get('title', '')}: {ev} [{cites}]")
        return " ".join(bullets[:3])
    
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        bullets = []
        for f in findings[:5]:
            cites = ", ".join(f.get("citations", []))
            ev = " ".join(f.get("evidence", [])[:1])
            bullets.append(f"- {f.get('title', '')}: {ev} [{cites}]")
        
        tl = [f"- {t.get('date')}: {t.get('event')} ({', '.join(t.get('citations', []))})" for t in timeline[:6]]
        
        prompt = (
            "You are a factual research summarizer. Synthesize the evidence into a crisp 120–180 word executive summary. "
            "Every concrete claim must be attributable to the given bullets or timeline (citations like TROVE:ID stay). "
            "Do not invent facts. Keep it specific to the query.\n\n"
            f"Query:\n{query}\n\nBullets:\n" + "\n".join(bullets) + "\n\nTimeline:\n" + "\n".join(tl)
        )
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        # Fallback on error
        return f"Summary unavailable: {str(e)}"

