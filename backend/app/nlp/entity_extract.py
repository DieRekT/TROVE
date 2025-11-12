"""Entity extraction using spaCy with optional Wikipedia links."""
from __future__ import annotations
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Lazy load spaCy to avoid import errors if not installed
_nlp = None
_wikipedia_available = False

try:
    import wikipedia
    _wikipedia_available = True
except ImportError:
    logger.warning("wikipedia library not available, entity links will be disabled")

try:
    import spacy
    _spacy_available = True
except ImportError:
    logger.warning("spacy not available, entity extraction will be disabled")
    _spacy_available = False


def _load_nlp():
    """Lazy load spaCy model."""
    global _nlp
    if _nlp is None and _spacy_available:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("en_core_web_sm model not found. Run: python -m spacy download en_core_web_sm")
            _nlp = None
    return _nlp


def extract_entities(text: str) -> List[Dict]:
    """
    Extract named entities from text using spaCy.
    
    Args:
        text: Input text to extract entities from
        
    Returns:
        List of entity dicts with 'text', 'label', 'link' (optional), and 'count'
    """
    if not text or not isinstance(text, str):
        return []
    
    nlp = _load_nlp()
    if not nlp:
        return []
    
    try:
        doc = nlp(text)
        ents = []
        seen = set()
        
        for ent in doc.ents:
            # Filter to relevant entity types
            if ent.label_ in ("PERSON", "ORG", "GPE", "LOC", "EVENT", "FAC", "PRODUCT"):
                label = ent.label_
                name = ent.text.strip()
                
                # Deduplicate by (name, label)
                key = (name.lower(), label)
                if key in seen:
                    continue
                seen.add(key)
                
                link = None
                if _wikipedia_available:
                    try:
                        # Try to get Wikipedia page (with auto_suggest disabled for exact matches)
                        page = wikipedia.page(name, auto_suggest=False)
                        link = page.url
                    except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.RedirectError):
                        # Try with auto_suggest enabled
                        try:
                            page = wikipedia.page(name, auto_suggest=True)
                            link = page.url
                        except:
                            pass
                    except Exception as e:
                        logger.debug(f"Wikipedia lookup failed for '{name}': {e}")
                
                ents.append({
                    "text": name,
                    "label": label,
                    "link": link
                })
        
        return ents
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return []

