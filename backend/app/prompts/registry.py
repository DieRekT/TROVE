"""Prompt registry with versioning support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent


def load(namespace: str, name: str) -> str:
    """
    Load a prompt file from the registry.
    
    Args:
        namespace: Directory name (e.g., "archive_detective", "summarize")
        name: Filename (e.g., "system_v1.md", "router_v2.md")
        
    Returns:
        Prompt content as string
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    p = ROOT / namespace / name
    if not p.exists():
        raise FileNotFoundError(f"Prompt not found: {p}")
    return p.read_text(encoding="utf-8").strip()


def get_archive_detective_prompts(version: str | None = None) -> Tuple[str, str]:
    """
    Get Archive Detective system and router prompts.
    
    Args:
        version: Prompt version (defaults to env var or "v2")
        
    Returns:
        Tuple of (system_prompt, router_prompt)
    """
    if version is None:
        version = os.getenv("PROMPTS_ARCHIVE_DETECTIVE_VERSION", "v2")
    sys_msg = load("archive_detective", f"system_{version}.md")
    router = load("archive_detective", f"router_{version}.md")
    return sys_msg, router


def get_summarize_prompts(version: str | None = None) -> Tuple[str, str]:
    """
    Get summarization system and user prompts.
    
    Args:
        version: Prompt version (defaults to env var or "v2")
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    if version is None:
        version = os.getenv("PROMPTS_SUMMARIZE_VERSION", "v2")
    sys_msg = load("summarize", f"system_{version}.md")
    user_prompt = load("summarize", f"user_{version}.md")
    return sys_msg, user_prompt


def get_search_suggestions_prompts(version: str | None = None) -> Tuple[str, str]:
    """
    Get search suggestions system and user prompts.
    
    Args:
        version: Prompt version (defaults to env var or "v2")
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    if version is None:
        version = os.getenv("PROMPTS_SEARCH_SUGGESTIONS_VERSION", "v2")
    sys_msg = load("search_suggestions", f"system_{version}.md")
    user_prompt = load("search_suggestions", f"user_{version}.md")
    return sys_msg, user_prompt


def get_report_enhance_prompt(version: str | None = None) -> str:
    """
    Get report enhancement prompt.
    
    Args:
        version: Prompt version (defaults to env var or "v2")
        
    Returns:
        System prompt string
    """
    if version is None:
        version = os.getenv("PROMPTS_REPORT_ENHANCE_VERSION", "v2")
    return load("report_enhance", f"system_{version}.md")

