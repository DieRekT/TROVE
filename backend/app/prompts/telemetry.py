"""JSONL telemetry logging for AI actions."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _log_entry(
    log_file: str,
    prompt_version: str,
    input_summary: str,
    output_schema_ok: bool,
    notes: dict[str, Any] | None = None,
) -> None:
    """
    Write a log entry to a JSONL file.
    
    Args:
        log_file: Filename in logs/ directory (e.g., "ai_router.jsonl")
        prompt_version: Version of prompt used (e.g., "v2")
        input_summary: Summary of input (truncated if needed)
        output_schema_ok: Whether output matched expected schema
        notes: Additional metadata dict
    """
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "prompt_version": prompt_version,
        "input_summary": input_summary[:200] if input_summary else "",
        "output_schema_ok": output_schema_ok,
        "notes": notes or {},
    }
    
    log_path = LOGS_DIR / log_file
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_router(
    prompt_version: str,
    user_text: str,
    output: dict[str, Any] | None,
    is_valid: bool,
    chosen_action: str | None = None,
) -> None:
    """
    Log router action.
    
    Args:
        prompt_version: Prompt version used
        user_text: User input text
        output: Router output dict
        is_valid: Whether output matched schema
        chosen_action: Action chosen (command or "say")
    """
    notes = {}
    if chosen_action:
        notes["chosen_action"] = chosen_action
    if output:
        notes["has_command"] = "command" in output
        notes["has_say"] = "say" in output
    
    _log_entry(
        "ai_router.jsonl",
        prompt_version,
        user_text[:200],
        is_valid,
        notes,
    )


def log_summarize(
    prompt_version: str,
    len_in: int,
    len_out: int,
    has_dates: bool = False,
) -> None:
    """
    Log summarization action.
    
    Args:
        prompt_version: Prompt version used
        len_in: Input text length
        len_out: Output text length
        has_dates: Whether output includes dates
    """
    _log_entry(
        "summarize.jsonl",
        prompt_version,
        f"input_len={len_in}",
        True,
        {"len_in": len_in, "len_out": len_out, "has_dates": has_dates},
    )


def log_search_suggestions(
    prompt_version: str,
    topic: str,
    n_out: int,
    is_valid: bool,
) -> None:
    """
    Log search suggestions action.
    
    Args:
        prompt_version: Prompt version used
        topic: Topic searched
        n_out: Number of suggestions returned
        is_valid: Whether output was valid JSON array
    """
    _log_entry(
        "search_suggestions.jsonl",
        prompt_version,
        topic[:200],
        is_valid,
        {"n_out": n_out},
    )


def log_report_enhance(
    prompt_version: str,
    chars_in: int,
    chars_out: int,
    citation_count: int = 0,
) -> None:
    """
    Log report enhancement action.
    
    Args:
        prompt_version: Prompt version used
        chars_in: Input character count
        chars_out: Output character count
        citation_count: Number of citations added
    """
    _log_entry(
        "report_enhance.jsonl",
        prompt_version,
        f"input_chars={chars_in}",
        True,
        {"chars_in": chars_in, "chars_out": chars_out, "citation_count": citation_count},
    )

