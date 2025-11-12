"""Telemetry logging for prompt usage."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_router(version: str, user_input: str, output: dict[str, Any] | None, is_valid: bool, chosen_action: str | None) -> None:
    """Log router telemetry.
    
    Args:
        version: Prompt version used
        user_input: User input message
        output: Router output (may be None)
        is_valid: Whether output passed validation
        chosen_action: Action chosen ("command" or "say")
    """
    try:
        # Log at debug level to avoid spam
        logger.debug(
            f"Router telemetry: version={version}, valid={is_valid}, action={chosen_action}, "
            f"input_len={len(user_input)}, has_output={output is not None}"
        )
    except Exception:
        pass  # Don't fail on telemetry errors


def log_summarize(version: str, input_len: int, output_len: int, has_dates: bool) -> None:
    """Log summarize telemetry.
    
    Args:
        version: Prompt version used
        input_len: Input text length
        output_len: Output summary length
        has_dates: Whether output contains dates
    """
    try:
        # Log at debug level to avoid spam
        logger.debug(
            f"Summarize telemetry: version={version}, input_len={input_len}, "
            f"output_len={output_len}, has_dates={has_dates}"
        )
    except Exception:
        pass  # Don't fail on telemetry errors


def log_search_suggestions(version: str, topic: str, count: int, is_valid: bool) -> None:
    """Log search suggestions telemetry.
    
    Args:
        version: Prompt version used
        topic: Topic searched for
        count: Number of suggestions generated
        is_valid: Whether suggestions passed validation
    """
    try:
        # Log at debug level to avoid spam
        logger.debug(
            f"Search suggestions telemetry: version={version}, topic={topic[:50]}, "
            f"count={count}, valid={is_valid}"
        )
    except Exception:
        pass  # Don't fail on telemetry errors

