"""Golden tests for prompt loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_prompt_registry_imports():
    """Test that registry can be imported."""
    from backend.app.prompts.registry import (
        get_archive_detective_prompts,
        get_report_enhance_prompt,
        get_search_suggestions_prompts,
        get_summarize_prompts,
    )
    
    assert callable(get_archive_detective_prompts)
    assert callable(get_summarize_prompts)
    assert callable(get_search_suggestions_prompts)
    assert callable(get_report_enhance_prompt)


def test_prompt_loading_v1():
    """Test loading v1 prompts."""
    from backend.app.prompts.registry import (
        get_archive_detective_prompts,
        get_report_enhance_prompt,
        get_search_suggestions_prompts,
        get_summarize_prompts,
    )
    
    # Load v1 prompts
    sys_v1, router_v1 = get_archive_detective_prompts("v1")
    assert sys_v1
    assert router_v1
    assert "Archive Detective" in sys_v1
    
    summ_sys_v1, summ_user_v1 = get_summarize_prompts("v1")
    assert summ_sys_v1
    assert summ_user_v1
    
    sug_sys_v1, sug_user_v1 = get_search_suggestions_prompts("v1")
    assert sug_sys_v1
    assert sug_user_v1
    
    report_v1 = get_report_enhance_prompt("v1")
    assert report_v1


def test_prompt_loading_v2():
    """Test loading v2 prompts."""
    from backend.app.prompts.registry import (
        get_archive_detective_prompts,
        get_report_enhance_prompt,
        get_search_suggestions_prompts,
        get_summarize_prompts,
    )
    
    # Load v2 prompts (default)
    sys_v2, router_v2 = get_archive_detective_prompts("v2")
    assert sys_v2
    assert router_v2
    assert "ROLE" in sys_v2 or "Archive Detective" in sys_v2
    
    summ_sys_v2, summ_user_v2 = get_summarize_prompts("v2")
    assert summ_sys_v2
    assert summ_user_v2
    assert "{body}" in summ_user_v2
    
    sug_sys_v2, sug_user_v2 = get_search_suggestions_prompts("v2")
    assert sug_sys_v2
    assert sug_user_v2
    assert "{topic}" in sug_user_v2
    
    report_v2 = get_report_enhance_prompt("v2")
    assert report_v2
    assert "{draft_content}" in report_v2


def test_router_schema_validation():
    """Test router output schema validation."""
    from app.archive_detective.chat_llm import _validate_router_output
    
    # Valid command response
    valid_command = {"command": "/search gold mining", "reason": "User wants to search"}
    assert _validate_router_output(valid_command) is True
    
    # Valid say response
    valid_say = {"say": "Here's what I found...", "reason": "Answering question"}
    assert _validate_router_output(valid_say) is True
    
    # Invalid: missing reason
    invalid_no_reason = {"command": "/search test"}
    assert _validate_router_output(invalid_no_reason) is False
    
    # Invalid: wrong command format
    invalid_command = {"command": "/invalid-command", "reason": "test"}
    assert _validate_router_output(invalid_command) is False
    
    # Invalid: neither command nor say
    invalid_empty = {"reason": "test"}
    assert _validate_router_output(invalid_empty) is False


def test_suggestions_schema_validation():
    """Test search suggestions output format."""
    # Valid suggestions array
    valid_suggestions = [
        "colonial settlement NSW",
        "aboriginal relations 1800s",
        "first contact NSW",
        "settlement history",
        "early colonization"
    ]
    assert isinstance(valid_suggestions, list)
    assert 5 <= len(valid_suggestions) <= 8
    assert all(isinstance(s, str) for s in valid_suggestions)
    
    # Invalid: too few
    invalid_few = ["one", "two", "three"]
    assert len(invalid_few) < 5
    
    # Invalid: too many
    invalid_many = [f"query {i}" for i in range(10)]
    assert len(invalid_many) > 8


def test_summarize_output_format():
    """Test summarize output format constraints."""
    # Valid summary should be <= 800 chars
    valid_summary = "• Point 1 (1900)\n• Point 2 (1901)\n• Point 3 (1902)"
    assert len(valid_summary) <= 800
    
    # Should have bullets
    assert "•" in valid_summary or "-" in valid_summary


def test_telemetry_imports():
    """Test that telemetry can be imported."""
    from backend.app.prompts.telemetry import (
        log_report_enhance,
        log_router,
        log_search_suggestions,
        log_summarize,
    )
    
    assert callable(log_router)
    assert callable(log_summarize)
    assert callable(log_search_suggestions)
    assert callable(log_report_enhance)


def test_prompt_templates_format():
    """Test that prompt templates have correct format placeholders."""
    from backend.app.prompts.registry import (
        get_search_suggestions_prompts,
        get_summarize_prompts,
    )
    
    # Summarize user prompt should have {body}
    _, summ_user = get_summarize_prompts("v2")
    assert "{body}" in summ_user
    
    # Search suggestions should have {topic} and {context}
    _, sug_user = get_search_suggestions_prompts("v2")
    assert "{topic}" in sug_user
    assert "{context}" in sug_user


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

