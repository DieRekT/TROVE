"""Quote extraction from text using sentence-level analysis."""

import re
from typing import List

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extract_quotes(text: str, query_terms: List[str], max_quotes: int = 2) -> List[str]:
    """
    Extract relevant quotes (sentences) from text that maximize term overlap with query.
    
    Returns verbatim sentences (not paraphrases), hard limit 240 chars per quote.
    Deduplicates similar quotes.
    """
    if not text or not query_terms:
        return []
    
    # Normalize text
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    
    # Split into sentences
    sentences = SENT_SPLIT.split(normalized)
    
    # Score each sentence by term overlap
    scored = []
    for sent in sentences:
        sent_clean = sent.strip()
        if not sent_clean:
            continue
        
        sent_lower = sent_clean.lower()
        # Count how many query terms appear in this sentence
        score = sum(1 for term in query_terms if term in sent_lower)
        
        if score > 0:
            scored.append((score, sent_clean))
    
    # Sort by score (descending), then by length (descending)
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    
    # Select top quotes, deduplicate, enforce length limit
    out = []
    seen = set()
    
    for _, sent in scored:
        # Normalize for deduplication (lowercase, strip)
        sent_normalized = sent.lower().strip()
        
        # Check if too similar to existing quotes (simple check)
        is_duplicate = False
        for existing in seen:
            # If sentences share >80% of words, consider duplicate
            existing_words = set(existing.split())
            sent_words = set(sent_normalized.split())
            if len(existing_words) > 0 and len(sent_words) > 0:
                overlap = len(existing_words & sent_words) / max(len(existing_words), len(sent_words))
                if overlap > 0.8:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            # Enforce 240 char limit
            quote = sent if len(sent) <= 240 else sent[:240].rsplit(" ", 1)[0] + "…"
            out.append(quote)
            seen.add(sent_normalized)
            
            if len(out) >= max_quotes:
                break
    
    return out

