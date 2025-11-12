from __future__ import annotations
import os, json
from typing import Any
from pydantic import TypeAdapter
from openai import OpenAI
from ..models.deep_research import DeepResearchResponse

"""
This module runs a final 'polish & verify' pass using OpenAI Structured Outputs.
Input: a draft DeepResearchResponse (already verified via your DB + Trove ingest).
Output: a model-conformant DeepResearchResponse (schema-enforced).
"""

def _get_client():
    """Lazy initialization of OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)

SYSTEM = (
    "You are the Synthesis Pass for a verified research report. "
    "You MUST return JSON matching the provided JSON Schema exactly. "
    "Do not invent citations; keep only those present in the draft. "
    "Keep quotes as short sentences (<= 240 chars). "
    "Keep the timeline factual, sorted, and cite sources. "
    "Improve clarity, flow, and concision; correct formatting issues. "
    "Australian English; no markdown in fields."
)

def _schema_for(model_cls: Any) -> dict:
    # Pydantic v2 JSON schema
    return model_cls.model_json_schema()

def synthesize_final(draft: DeepResearchResponse, model: str = "gpt-4o-mini") -> DeepResearchResponse:
    client = _get_client()
    schema = _schema_for(DeepResearchResponse)
    # clamp large fields (defensive)
    draft_json = json.loads(draft.model_dump_json())

    # Use response_format for structured output (OpenAI API)
    # Note: json_schema format may not be available in all models, fallback to json_object
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps({
                    "instruction": "Return a cleaned and improved report JSON that VALIDATES against the schema.",
                    "draft_report": draft_json
                }, ensure_ascii=False)}
            ],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.3,
        )
    except Exception as e:
        # Fallback: try without structured output format
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM + " Return ONLY valid JSON, no markdown, no explanation."},
                {"role": "user", "content": json.dumps({
                    "instruction": "Return a cleaned and improved report JSON that VALIDATES against the schema.",
                    "draft_report": draft_json
                }, ensure_ascii=False) + "\n\nIMPORTANT: Return ONLY valid JSON matching the schema."}
            ],
            max_tokens=4096,
            temperature=0.3,
        )

    # Extract JSON from response
    text = completion.choices[0].message.content
    data = json.loads(text)

    # Validate back into Pydantic model
    ta = TypeAdapter(DeepResearchResponse)
    return ta.validate_python(data)

