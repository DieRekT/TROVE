from __future__ import annotations

from typing import Any, Dict, List


def is_valid_router(obj: Dict[str, Any]) -> bool:
    """Validate router JSON response.
    
    Args:
        obj: Dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(obj, dict):
        return False
    
    keys = set(obj.keys())
    
    # Must have exactly one of "command" or "say"
    if not (("command" in obj) ^ ("say" in obj)):
        return False
    
    # Must have "reason"
    if "reason" not in obj:
        return False
    
    # Only allowed keys
    if not set(keys).issubset({"command", "say", "reason"}):
        return False
    
    # Validate types
    if "command" in obj and not isinstance(obj["command"], str):
        return False
    
    if "say" in obj and not isinstance(obj["say"], str):
        return False
    
    if not isinstance(obj["reason"], str) or len(obj["reason"]) == 0:
        return False
    
    return True


def is_valid_suggestions(arr: Any) -> bool:
    """Validate search suggestions array.
    
    Args:
        arr: Array to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(arr, list):
        return False
    
    # Must have 5-8 items
    if not (5 <= len(arr) <= 8):
        return False
    
    # All items must be non-empty strings
    return all(isinstance(x, str) and x.strip() for x in arr)

