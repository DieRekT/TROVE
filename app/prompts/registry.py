from __future__ import annotations

from pathlib import Path
from typing import Tuple


ROOT = Path(__file__).resolve().parent


def load(namespace: str, name: str) -> str:
    """Load a prompt file from the prompts directory.
    
    Args:
        namespace: Subdirectory name (e.g., 'archive_detective')
        name: File name (e.g., 'system_v2.md')
        
    Returns:
        Prompt text as string
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    p = ROOT / namespace / name
    if not p.exists():
        raise FileNotFoundError(f"Prompt not found: {p}")
    return p.read_text(encoding="utf-8").strip()


def get_archive_detective_prompts(version: str | None = None) -> Tuple[str, str]:
    """Get Archive Detective system and router prompts.
    
    Args:
        version: Prompt version (defaults to "v2" or PROMPTS_ARCHIVE_DETECTIVE_VERSION env var)
        
    Returns:
        Tuple of (system_prompt, router_prompt)
    """
    import os
    if version is None:
        version = os.getenv("PROMPTS_ARCHIVE_DETECTIVE_VERSION", "v2")
    sys_msg = load("archive_detective", f"system_{version}.md")
    router = load("archive_detective", f"router_{version}.md")
    return sys_msg, router


def get_summarize_prompts(version: str | None = None) -> Tuple[str, str]:
    """Get summarize system and user prompts.
    
    Args:
        version: Prompt version (defaults to "v2" or PROMPTS_SUMMARIZE_VERSION env var)
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import os
    if version is None:
        version = os.getenv("PROMPTS_SUMMARIZE_VERSION", "v2")
    return load("summarize", f"system_{version}.md"), load("summarize", f"user_{version}.md")


def get_search_suggestions_prompts(version: str | None = None) -> Tuple[str, str]:
    """Get search suggestions system and user prompts.
    
    Args:
        version: Prompt version (defaults to "v2" or PROMPTS_SEARCH_SUGGESTIONS_VERSION env var)
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import os
    if version is None:
        version = os.getenv("PROMPTS_SEARCH_SUGGESTIONS_VERSION", "v2")
    return load("search_suggestions", f"system_{version}.md"), load("search_suggestions", f"user_{version}.md")


def get_report_enhance_prompt(version: str | None = None) -> str:
    """Get report enhancement prompt.
    
    Args:
        version: Prompt version (defaults to "v2" or PROMPTS_REPORT_ENHANCE_VERSION env var)
        
    Returns:
        Report enhancement prompt text
    """
    import os
    if version is None:
        version = os.getenv("PROMPTS_REPORT_ENHANCE_VERSION", "v2")
    return load("report_enhance", f"system_{version}.md")

