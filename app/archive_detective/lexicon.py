"""Historical terms lexicon for sensitive research mode."""

import json
from pathlib import Path
from typing import Any

LEXICON = None


def load_lexicon() -> dict[str, Any]:
    """Load historical terms lexicon from JSON file."""
    global LEXICON
    if LEXICON:
        return LEXICON
    
    # Try multiple paths
    paths = [
        Path(__file__).parent.parent.parent / "packages" / "lexicon" / "historical_terms.json",
        Path(__file__).parent.parent / "packages" / "lexicon" / "historical_terms.json",
        Path("packages/lexicon/historical_terms.json"),
    ]
    
    for path in paths:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    LEXICON = json.load(f)
                    return LEXICON
            except Exception:
                continue
    
    # Return empty lexicon if not found
    LEXICON = {"entries": []}
    return LEXICON


def expand_query(q: str, sensitive: bool) -> str:
    """
    Expand query with historical/offensive terms if sensitive mode is enabled.
    
    Args:
        q: Original query string
        sensitive: Whether to expand with historical terms
        
    Returns:
        Expanded query string (OR boolean query)
    """
    if not sensitive:
        return q
    
    lex = load_lexicon()
    expansions = []
    q_lower = q.lower()
    
    for entry in lex.get("entries", []):
        triggers = entry.get("triggers", [])
        if any(trigger in q_lower for trigger in triggers):
            expansions.extend(entry.get("include_terms", []))
    
    if expansions:
        # Remove duplicates and sort
        unique_expansions = sorted(set(expansions))
        # Quote terms with spaces
        quoted_expansions = [
            f'"{term}"' if " " in term else term
            for term in unique_expansions
        ]
        exp_str = " OR ".join(quoted_expansions)
        return f"({q}) OR ({exp_str})"
    
    return q


