"""OpenAI Responses API wrapper with Structured Outputs support."""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

OPENAI_BASE = "https://api.openai.com/v1"
OPENAI_MODEL_PRIMARY = os.getenv("OPENAI_MODEL_PRIMARY", "gpt-4o")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4o-mini")
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "800"))


def _get_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return key


async def synthesize_research(
    query: str,
    sources: list[Dict[str, Any]],
    depth: str = "standard",
) -> Dict[str, Any]:
    """
    Use OpenAI Responses API with Structured Outputs to synthesize research report.
    
    Args:
        query: Research question
        sources: List of source dicts with id, title, year, url, snippets
        depth: Research depth (brief|standard|deep)
    
    Returns:
        Dict with executive_summary, key_findings, timeline
    """
    api_key = _get_api_key()
    
    # Build context from sources (top ~8)
    top_sources = sources[:8]
    context_parts = []
    for src in top_sources:
        src_id = src.get("id", "UNKNOWN")
        src_title = src.get("title", "Untitled")
        src_year = src.get("year")
        src_url = src.get("url", "")
        src_snippets = src.get("snippets", [])
        
        src_text = f"Source: {src_id}\nTitle: {src_title}\n"
        if src_year:
            src_text += f"Year: {src_year}\n"
        if src_url:
            src_text += f"URL: {src_url}\n"
        if src_snippets:
            src_text += "Quotes:\n" + "\n".join(f"  - {q}" for q in src_snippets[:2])
        context_parts.append(src_text)
    
    context = "\n\n".join(context_parts)
    
    # Determine output length based on depth
    if depth == "brief":
        max_findings = 3
        summary_words = 180
    elif depth == "deep":
        max_findings = 5
        summary_words = 300
    else:  # standard
        max_findings = 4
        summary_words = 240
    
    # System instruction
    system_prompt = f"""You are a research synthesis assistant. Your task is to analyze sources and create a grounded research report.

CRITICAL RULES:
1. Ground ALL claims in the provided SOURCES. Never invent facts, dates, or quotes.
2. Use VERBATIM quotes from sources (evidence field). Keep quotes ≤240 characters.
3. Every finding MUST include at least one citation (source id like TROVE:... or WEB:...).
4. Timeline dates should be ISO format (YYYY-MM-DD) when available, or YYYY-MM-01 if only year is known.
5. Executive summary should be concise ({summary_words} words max), reference the period/region if provided.
6. Extract 3-{max_findings} key findings, each with title, insight, evidence (quotes), and citations.
7. Build a chronological timeline from the sources.

If sources are thin or contradictory, state that in the summary. Never fabricate information."""

    user_prompt = f"""Research Question: {query}

SOURCES:
{context}

Synthesize a research report with:
1. Executive Summary ({summary_words} words max)
2. {max_findings} Key Findings (each with title, insight, evidence quotes, citations)
3. Timeline (chronological events with dates and citations)

Return JSON matching this schema:
{{
  "executive_summary": "string (≤{summary_words} words)",
  "key_findings": [
    {{
      "title": "string",
      "insight": "string (2-3 sentences)",
      "evidence": ["verbatim quote 1", "verbatim quote 2"],
      "citations": ["TROVE:...", "WEB:..."],
      "confidence": 0.0-1.0
    }}
  ],
  "timeline": [
    {{
      "date": "YYYY-MM-DD or YYYY-MM-01",
      "event": "string",
      "citations": ["TROVE:..."]
    }}
  ]
}}"""

    # JSON Schema for structured output
    json_schema = {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "key_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "insight": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "citations": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["title", "insight", "evidence", "citations", "confidence"],
                },
            },
            "timeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "event": {"type": "string"},
                        "citations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["date", "event", "citations"],
                },
            },
        },
        "required": ["executive_summary", "key_findings", "timeline"],
    }
    
    # Try primary model first
    model = OPENAI_MODEL_PRIMARY
    try:
        result = await _call_openai(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=json_schema,
            max_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        )
        return result
    except Exception as e:
        logger.warning(f"Primary model {model} failed: {e}, trying fallback")
        # Try fallback
        model = OPENAI_MODEL_FALLBACK
        try:
            result = await _call_openai(
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=json_schema,
                max_tokens=OPENAI_MAX_OUTPUT_TOKENS,
            )
            return result
        except Exception as e2:
            logger.error(f"Both models failed: {e2}")
            # Return deterministic fallback
            return _fallback_synthesis(query, sources, depth)


async def _call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: Dict[str, Any],
    max_tokens: int,
) -> Dict[str, Any]:
    """Call OpenAI Chat Completions API with response_format for structured output."""
    url = f"{OPENAI_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Use json_object for models that support it, otherwise rely on prompt
    # For newer models (gpt-4o, o1, o3), we can use json_schema
    # For older models, use json_object
    if "gpt-4o" in model or "o1" in model or "o3" in model:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
    else:
        # Fallback: request JSON in prompt
        user_prompt_with_json = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON, no markdown, no explanation."
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt + " Always return valid JSON only."},
                {"role": "user", "content": user_prompt_with_json},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
    
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract content from response
        content = data["choices"][0]["message"]["content"]
        
        # Parse JSON
        try:
            parsed = json.loads(content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI: {e}, content: {content[:200]}")
            raise RuntimeError(f"Invalid JSON from OpenAI: {e}")


def _fallback_synthesis(
    query: str,
    sources: list[Dict[str, Any]],
    depth: str,
) -> Dict[str, Any]:
    """Deterministic fallback when LLM is unavailable."""
    logger.warning("Using fallback synthesis (LLM unavailable)")
    
    top_sources = sources[:5]
    
    # Simple executive summary
    exec_summary = f"This report synthesizes {len(sources)} sources related to '{query}'. "
    if top_sources:
        exec_summary += f"Key sources include: {', '.join(s.get('title', 'Untitled')[:50] for s in top_sources[:3])}."
    exec_summary += " Evidence may be limited; verify claims with primary sources."
    
    # Simple findings from top sources
    findings = []
    for i, src in enumerate(top_sources[:4], 1):
        snippets = src.get("snippets", [])
        evidence = snippets[:2] if snippets else []
        findings.append({
            "title": src.get("title", f"Finding {i}"),
            "insight": f"Source {src.get('id', 'UNKNOWN')} provides relevant information about '{query}'.",
            "evidence": evidence,
            "citations": [src.get("id", "UNKNOWN")],
            "confidence": 0.5,
        })
    
    # Simple timeline
    timeline = []
    for src in top_sources:
        year = src.get("year")
        if year:
            timeline.append({
                "date": f"{year}-01-01",
                "event": src.get("title", "Event")[:120],
                "citations": [src.get("id", "UNKNOWN")],
            })
    
    timeline.sort(key=lambda x: x["date"])
    
    return {
        "executive_summary": exec_summary,
        "key_findings": findings,
        "timeline": timeline,
    }

