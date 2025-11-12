#!/usr/bin/env python3
import httpx, logging, time
from typing import List, Dict

logger = logging.getLogger(__name__)

TROVE_URL = "https://api.trove.nla.gov.au/v3/result"

def extract_articles(data: dict) -> List[Dict]:
    try:
        records = (
            data.get("category", [{}])[0]
            .get("records", {})
            .get("article", [])
        )
        return [
            {
                "id": a.get("id"),
                "title": a.get("heading"),
                "date": a.get("date"),
                "source": a.get("title", {}).get("value"),
                "snippet": a.get("snippet"),
                "url": f"https://nla.gov.au/{a.get('id')}",
            }
            for a in records
            if a.get("id")
        ]
    except Exception as e:
        logger.warning(f"extract_articles error: {e}")
        return []

def fetch_many(query: str, api_key: str, pages: int = 5, delay: float = 0.5) -> List[Dict]:
    """Fetch up to pages×100 Trove articles."""
    results: List[Dict] = []
    with httpx.Client(timeout=20) as client:
        for page in range(pages):
            start = page * 100 + 1
            params = {
                "q": query,
                "category": "newspaper",
                "encoding": "json",
                "reclevel": "brief",
                "n": 100,
                "s": start,
                "key": api_key,
            }
            try:
                r = client.get(TROVE_URL, params=params)
                r.raise_for_status()
                chunk = extract_articles(r.json())
                results.extend(chunk)
                logger.info(f"Trove page {page+1}: {len(chunk)} items")
                if len(chunk) < 100:
                    break
                time.sleep(delay)
            except Exception as e:
                logger.warning(f"Trove fetch page {page}: {e}")
                break
    logger.info(f"Fetched total {len(results)} records for '{query}'")
    return results

