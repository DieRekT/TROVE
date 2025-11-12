"""Golden tests for prompt registry and validators."""

from __future__ import annotations

import json

import pytest

from app.prompts.registry import (
    get_archive_detective_prompts,
    get_summarize_prompts,
    get_search_suggestions_prompts,
    get_report_enhance_prompt,
)
from app.utils.validators import is_valid_router, is_valid_suggestions


def test_registry_loads_archive_detective_prompts():
    """Test that archive detective prompts load correctly."""
    sys, router = get_archive_detective_prompts("v2")
    
    assert sys is not None
    assert router is not None
    assert len(sys) > 0
    assert len(router) > 0
    assert "Archive Detective" in sys
    assert "convert user input" in router.lower() or "json" in router.lower()


def test_registry_loads_summarize_prompts():
    """Test that summarize prompts load correctly."""
    sys, user = get_summarize_prompts("v2")
    
    assert sys is not None
    assert user is not None
    assert len(sys) > 0
    assert len(user) > 0
    assert "factual" in sys.lower() or "bullets" in sys.lower()
    assert "{body}" in user


def test_registry_loads_search_suggestions_prompts():
    """Test that search suggestions prompts load correctly."""
    sys, user = get_search_suggestions_prompts("v2")
    
    assert sys is not None
    assert user is not None
    assert len(sys) > 0
    assert len(user) > 0
    assert "json" in sys.lower() or "array" in sys.lower()
    assert "{topic}" in user
    assert "{context}" in user


def test_registry_loads_report_enhance_prompt():
    """Test that report enhance prompt loads correctly."""
    prompt = get_report_enhance_prompt("v2")
    
    assert prompt is not None
    assert len(prompt) > 0
    assert "enhance" in prompt.lower() or "improve" in prompt.lower()


def test_router_json_shape_valid():
    """Test that valid router JSON passes validation."""
    # Valid command response
    obj = {"command": "/search Sandon River mining", "reason": "Finds sources"}
    assert is_valid_router(obj)
    
    # Valid say response
    obj = {"say": "According to the article...", "reason": "Answers question"}
    assert is_valid_router(obj)
    
    # Both command and say (should fail)
    obj = {"command": "/search test", "say": "test", "reason": "test"}
    assert not is_valid_router(obj)
    
    # Missing reason (should fail)
    obj = {"command": "/search test"}
    assert not is_valid_router(obj)
    
    # Invalid keys (should fail)
    obj = {"command": "/search test", "reason": "test", "extra": "key"}
    assert not is_valid_router(obj)
    
    # Empty reason (should fail)
    obj = {"command": "/search test", "reason": ""}
    assert not is_valid_router(obj)


def test_suggestions_shape_valid():
    """Test that valid suggestions array passes validation."""
    # Valid suggestions (5-8 items)
    arr = [
        "gold mining Sandon River",
        "Sandon quartz reef 1890s",
        "sluicing Sandon",
        "alluvial gold Sandon",
        "Sandon River prospecting",
    ]
    assert is_valid_suggestions(arr)
    
    # Valid suggestions (8 items)
    arr = ["query1", "query2", "query3", "query4", "query5", "query6", "query7", "query8"]
    assert is_valid_suggestions(arr)
    
    # Too few items (should fail)
    arr = ["query1", "query2", "query3", "query4"]
    assert not is_valid_suggestions(arr)
    
    # Too many items (should fail)
    arr = ["query1", "query2", "query3", "query4", "query5", "query6", "query7", "query8", "query9"]
    assert not is_valid_suggestions(arr)
    
    # Empty strings (should fail)
    arr = ["query1", "query2", "query3", "query4", ""]
    assert not is_valid_suggestions(arr)
    
    # Not a list (should fail)
    assert not is_valid_suggestions("not a list")
    assert not is_valid_suggestions({"key": "value"})


def test_router_json_shape_example():
    """Test example router JSON responses."""
    # Minimal sanity: model call not executed here; just schema helper example
    obj = {"command": "/search Sandon River mining", "reason": "Finds sources"}
    assert is_valid_router(obj)


def test_suggestions_shape_example():
    """Test example suggestions array."""
    arr = [
        "gold mining Sandon River",
        "Sandon quartz reef 1890s",
        "sluicing Sandon",
        "alluvial gold Sandon",
        "Sandon River prospecting",
    ]
    assert is_valid_suggestions(arr)


def test_prompts_are_non_empty():
    """Test that all prompts are non-empty."""
    sys, router = get_archive_detective_prompts("v2")
    assert len(sys.strip()) > 0
    assert len(router.strip()) > 0
    
    sys, user = get_summarize_prompts("v2")
    assert len(sys.strip()) > 0
    assert len(user.strip()) > 0
    
    sys, user = get_search_suggestions_prompts("v2")
    assert len(sys.strip()) > 0
    assert len(user.strip()) > 0
    
    prompt = get_report_enhance_prompt("v2")
    assert len(prompt.strip()) > 0

