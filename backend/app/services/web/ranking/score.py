"""Advanced scoring: BM25-lite + domain reputation + recency + diversity."""

import logging
import math
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta

from ....models.web_search import WebSearchResult

logger = logging.getLogger(__name__)

# Domain reputation scores
DOMAIN_REPUTATION_MAP = {
    # High reputation (.gov, .edu, .org)
    ".gov.au": 0.2,
    ".gov": 0.2,
    ".edu": 0.2,
    ".edu.au": 0.2,
    ".org": 0.15,
    ".org.au": 0.15,
    
    # Specific trusted domains
    "nla.gov.au": 0.25,
    "abs.gov.au": 0.25,
    "trove.nla.gov.au": 0.25,
    
    # Reputable news domains (add more as needed)
    "abc.net.au": 0.1,
    "theguardian.com": 0.1,
    "smh.com.au": 0.1,
    "theage.com.au": 0.1,
    "afr.com": 0.1,
}

# Spammy TLDs (penalty)
SPAM_TLDS = {".xyz", ".top", ".click", ".download", ".stream"}


def _bm25lite(text: str, terms: List[str]) -> float:
    """
    BM25-lite scoring for relevance.
    
    Simplified BM25 that works on term frequency and document length.
    """
    if not text or not terms:
        return 0.0
    
    text_lower = text.lower()
    doc_length = max(1, len(text_lower.split()))
    
    score = 0.0
    unique_terms = set(terms)
    
    for term in unique_terms:
        term_freq = text_lower.count(term)
        if term_freq > 0:
            # BM25-lite formula: tf * idf-like boost
            # k1 = 1.5, b = 0.75 (standard BM25 parameters)
            tf_score = (term_freq / (term_freq + 1.5))
            length_norm = 1.2 * (1 + 0.75 * (1000 / doc_length))
            score += tf_score * length_norm
    
    return score


def get_domain_reputation(url: str) -> float:
    """
    Get domain reputation score based on TLD and known domains.
    
    Returns:
        - 0.2 for .gov/.edu/.org
        - 0.1 for reputable news domains
        - -0.1 penalty for spammy TLDs
        - 0.0 default
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check specific domains first
        for trusted_domain, score in DOMAIN_REPUTATION_MAP.items():
            if trusted_domain in domain:
                return score
        
        # Check TLD
        if domain.endswith(".gov.au") or domain.endswith(".gov"):
            return 0.2
        if domain.endswith(".edu.au") or domain.endswith(".edu"):
            return 0.2
        if domain.endswith(".org.au") or domain.endswith(".org"):
            return 0.15
        
        # Check for spam TLDs
        for spam_tld in SPAM_TLDS:
            if domain.endswith(spam_tld):
                return -0.1
        
        return 0.0
        
    except Exception as e:
        logger.debug(f"Error parsing domain from {url}: {e}")
        return 0.0


def _recency_boost(date_str: Optional[str], prefer_recent: bool = False) -> float:
    """
    Calculate recency boost if date is available and prefer_recent is True.
    
    Formula: (1 / log(1 + age_days)) * α
    where α = 0.1 (boost factor)
    """
    if not prefer_recent or not date_str:
        return 0.0
    
    try:
        # Try to parse date (various formats)
        date_obj = None
        for fmt in ["%Y-%m-%d", "%Y-%m", "%Y", "%d/%m/%Y", "%m/%d/%Y"]:
            try:
                date_obj = datetime.strptime(date_str[:10], fmt)
                break
            except ValueError:
                continue
        
        if not date_obj:
            return 0.0
        
        age_days = (datetime.now() - date_obj).days
        if age_days < 0:
            age_days = 0  # Future dates
        
        if age_days == 0:
            return 0.15  # Very recent
        
        # Boost formula: (1 / log(1 + age_days)) * 0.1
        boost = (1.0 / math.log(1 + age_days)) * 0.1
        return min(boost, 0.15)  # Cap at 0.15
        
    except Exception:
        return 0.0


def _diversity_penalty(domain: str, seen_domains: Dict[str, int]) -> float:
    """
    Apply diversity penalty for duplicate domains.
    
    -0.1 for each duplicate domain beyond the first.
    """
    if not domain:
        return 0.0
    
    count = seen_domains.get(domain, 0)
    if count == 0:
        seen_domains[domain] = 1
        return 0.0
    
    seen_domains[domain] = count + 1
    return -0.1 * count  # Increasing penalty for more duplicates


def calculate_relevance_score(
    result: WebSearchResult,
    query: str,
    query_terms: List[str],
    prefer_recent: bool = False,
    seen_domains: Optional[Dict[str, int]] = None,
) -> float:
    """
    Calculate comprehensive relevance score.
    
    Components:
    1. BM25-lite on (title + snippet + extracted_text)
    2. Domain reputation (+0.2 for .gov/.edu, etc.)
    3. Recency boost (if prefer_recent and date available)
    4. Diversity penalty (-0.1 per duplicate domain)
    
    Final: clamp(BM25 + domain + recency - diversity, 0..1.5)
    """
    if seen_domains is None:
        seen_domains = {}
    
    # Combine text fields for BM25
    combined_text = " ".join([
        result.title,
        result.snippet,
        result.extracted_text or "",
    ])
    
    # 1. BM25-lite score
    bm25_score = _bm25lite(combined_text, query_terms)
    
    # 2. Domain reputation
    domain_rep = get_domain_reputation(result.url)
    result.domain_reputation = domain_rep
    
    # 3. Recency boost
    recency = _recency_boost(result.date, prefer_recent)
    
    # 4. Diversity penalty
    diversity_penalty = _diversity_penalty(result.domain, seen_domains)
    
    # Combine scores
    final_score = bm25_score + domain_rep + recency - abs(diversity_penalty)
    
    # Clamp to 0..1.5
    final_score = max(0.0, min(1.5, final_score))
    
    return final_score

