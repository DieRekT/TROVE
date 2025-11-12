#!/usr/bin/env python3
"""
Seed the Trove research context store with curated sample data and exercise key
FastAPI endpoints so there is always a baseline of research and brief cards
available for manual testing.

The script:
1. Ensures the SQLite schema has the tables/columns the app expects.
2. Inserts a set of thematic research articles, cards, and imagery.
3. Uses FastAPI's TestClient (with a stubbed Trove client) to run through the
   main pin, card, summary, and brief endpoints.
4. Captures the responses and stored records to app/data/sample_briefs.json.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi.testclient import TestClient

# Ensure a Trove API key is present before importing the app.  We stub the
# client later, but settings validation happens on import.
os.environ.setdefault("TROVE_API_KEY", "DUMMY_API_KEY_FOR_SMOKE_TESTS")

# Add project root to sys.path for direct script execution.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.context_store import (  # noqa: E402
    DB_PATH,
    ensure_db,
    list_articles,
    list_kingfisher_cards,
    save_article_images,
    save_kingfisher_cards,
    set_pinned,
    touch_session,
    upsert_item,
)
from app.dependencies import get_trove_client  # noqa: E402
from app.main import app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed-sample-research")

SESSION_ID = "seed-sample-session"
SESSION_HEADERS = {
    "X-Session-Id": SESSION_ID,
    "User-Agent": "SeedSampleResearch/1.0",
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "sample_briefs.json"


def _ensure_extended_schema() -> None:
    """Make sure auxiliary tables/columns exist in the context database."""
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kingfisher_cards(
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                card_type TEXT NOT NULL,
                title TEXT,
                content TEXT,
                metadata TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS article_images(
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                source TEXT,
                source_url TEXT,
                local_path TEXT,
                width INTEGER,
                height INTEGER,
                generated INTEGER NOT NULL DEFAULT 0,
                metadata TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )

        # Add richer article columns if they are missing.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(articles);")}
        alter_statements = []
        if "full_text" not in columns:
            alter_statements.append("ALTER TABLE articles ADD COLUMN full_text TEXT;")
        if "summary" not in columns:
            alter_statements.append("ALTER TABLE articles ADD COLUMN summary TEXT;")
        if "summary_bullets" not in columns:
            alter_statements.append("ALTER TABLE articles ADD COLUMN summary_bullets TEXT;")
        for statement in alter_statements:
            conn.execute(statement)
        conn.commit()


def _store_rich_article_fields(
    sid: str,
    article_id: str,
    *,
    full_text: str,
    summary: str | None = None,
    summary_bullets: Iterable[str] | None = None,
) -> None:
    """Persist extended text fields without disturbing the other article data."""
    bullets_json = json.dumps(list(summary_bullets or []))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE articles
            SET full_text=?, summary=?, summary_bullets=?, last_seen=strftime('%s','now')
            WHERE sid=? AND trove_id=?
            """,
            (full_text, summary, bullets_json, sid, article_id),
        )
        conn.commit()


SAMPLE_TOPICS: List[Dict[str, Any]] = [
    {
        "query": "great barrier reef conservation",
        "category": "newspaper",
        "articles": [
            {
                "trove_id": "184199164",
                "trove_page_id": "16272168",
                "title": "Scientists Warn Of Reef Bleaching",
                "date": "1922-03-15",
                "source": "The Argus (Melbourne, Vic.)",
                "url": "https://nla.gov.au/nla.news-article184199164",
                "snippet": "Marine biologists report unprecedented coral bleaching across key sections of the Great Barrier Reef.",
                "full_text": (
                    "Marine biologists stationed along the Barrier Reef reported extensive bleaching "
                    "following a month of exceptionally warm waters. Conservation groups urged federal "
                    "support for monitoring programs and highlighted the need for temperature records."
                ),
                "pinned": True,
                "cards": [
                    {
                        "type": "event",
                        "title": "Bleaching Survey Conducted",
                        "content": "A coordinated survey documented coral bleaching across thirty reef sites after prolonged heat.",
                        "metadata": {"year": 1922, "location": "Great Barrier Reef"},
                    },
                    {
                        "type": "person",
                        "title": "Dr. Edith McKellar",
                        "content": "Marine biologist advocating for federal conservation funding and continuous reef observation.",
                        "metadata": {"role": "Marine biologist"},
                    },
                    {
                        "type": "quote",
                        "title": "Urgent Plea",
                        "content": "\"Without timely intervention, we risk losing the reef that defines our northern coastline.\"",
                        "metadata": {"speaker": "Dr. Edith McKellar"},
                    },
                ],
                "images": [
                    {
                        "kind": "primary",
                        "source": "Illustrated London News Archive",
                        "source_url": "https://example.org/images/reef_survey.jpg",
                        "width": 1200,
                        "height": 800,
                        "metadata": {"caption": "Scientists documenting coral bleaching in 1922."},
                    }
                ],
                "summary": "Survey teams observed bleaching across thirty reef locations after anomalous warm currents.",
                "summary_bullets": [
                    "Federal funding requested for reef monitoring.",
                    "Heat anomalies linked to widespread bleaching.",
                    "Calls for national conservation coordination.",
                ],
            },
            {
                "trove_id": "217845321",
                "trove_page_id": "19900421",
                "title": "Queensland Communities Rally For Reef",
                "date": "1954-09-02",
                "source": "The Courier-Mail (Brisbane, Qld.)",
                "url": "https://nla.gov.au/nla.news-article217845321",
                "snippet": "Local councils coordinated a letter-writing campaign urging reef protections amid tourism expansion.",
                "full_text": (
                    "Representatives from coastal shires met in Townsville to address reef preservation. "
                    "They resolved to lobby the Commonwealth for stricter fishing controls and education campaigns "
                    "aimed at visiting tourists and shipping companies."
                ),
                "pinned": False,
                "cards": [
                    {
                        "type": "event",
                        "title": "Townsville Preservation Meeting",
                        "content": "Coastal shires met in Townsville to petition for national reef protections.",
                        "metadata": {"year": 1954},
                    },
                    {
                        "type": "place",
                        "title": "Townsville Shire Hall",
                        "content": "Venue for the Queensland coastal symposium on reef safeguards.",
                        "metadata": {"state": "Queensland"},
                    },
                ],
                "images": [],
                "summary": "Queensland councils organised coordinated advocacy for reef protections amid tourism growth.",
                "summary_bullets": [
                    "Regional alliance formed to lobby Canberra.",
                    "Tourism pressures identified as emerging risk.",
                ],
            },
        ],
    },
    {
        "query": "australian women's suffrage campaign",
        "category": "newspaper",
        "articles": [
            {
                "trove_id": "201938475",
                "trove_page_id": "14533210",
                "title": "Delegation Carries Suffrage Petition",
                "date": "1893-07-28",
                "source": "The Advertiser (Adelaide, SA)",
                "url": "https://nla.gov.au/nla.news-article201938475",
                "snippet": "South Australian suffragists presented a petition with over 11,000 signatures to parliament.",
                "full_text": (
                    "The Women's Suffrage League delivered a petition exceeding 11,000 signatures to the South "
                    "Australian Parliament, arguing that women's enfranchisement would strengthen democratic principles "
                    "and improve social legislation."
                ),
                "pinned": True,
                "cards": [
                    {
                        "type": "event",
                        "title": "Petition Presented",
                        "content": "A petition with 11,000 signatures reached the South Australian House of Assembly.",
                        "metadata": {"year": 1893},
                    },
                    {
                        "type": "person",
                        "title": "Mary Lee",
                        "content": "Veteran organiser who coordinated rural petition drives for the suffrage campaign.",
                        "metadata": {"role": "Suffrage organiser"},
                    },
                    {
                        "type": "quote",
                        "title": "Call For Equality",
                        "content": "\"We claim the vote as a matter of simple justice.\"",
                        "metadata": {"speaker": "Mary Lee"},
                    },
                ],
                "images": [
                    {
                        "kind": "primary",
                        "source": "State Library of South Australia",
                        "source_url": "https://example.org/images/suffrage_petition.jpg",
                        "width": 1024,
                        "height": 768,
                        "metadata": {"caption": "Members of the Women's Suffrage League outside parliament."},
                    }
                ],
                "summary": "South Australian suffragists advanced a mass petition advocating for women's enfranchisement.",
                "summary_bullets": [
                    "Petition surpassed 11,000 signatures.",
                    "Mary Lee highlighted equity and civic duty.",
                ],
            },
            {
                "trove_id": "208877120",
                "trove_page_id": "15000987",
                "title": "Federation Convention Debates Women's Vote",
                "date": "1902-03-05",
                "source": "The Sydney Morning Herald (NSW)",
                "url": "https://nla.gov.au/nla.news-article208877120",
                "snippet": "Delegates discussed incorporating women's suffrage into the Commonwealth franchise legislation.",
                "full_text": (
                    "Parliamentary debates in Melbourne grappled with ensuring women across the new Commonwealth "
                    "would enjoy a uniform franchise. Proponents cited New Zealand's example and the success of "
                    "South Australia's reforms."
                ),
                "pinned": False,
                "cards": [
                    {
                        "type": "event",
                        "title": "Commonwealth Franchise Bill Debate",
                        "content": "Federal legislators debated including women's suffrage in the new franchise act.",
                        "metadata": {"year": 1902},
                    },
                    {
                        "type": "person",
                        "title": "Vida Goldstein",
                        "content": "Campaigner observing the federal debates and lobbying delegates for a universal vote.",
                        "metadata": {"role": "Advocate"},
                    },
                ],
                "images": [],
                "summary": "Commonwealth parliament considered universal suffrage, building on earlier colonial reforms.",
                "summary_bullets": [
                    "Delegates referenced New Zealand's precedent.",
                    "Advocates argued for national consistency.",
                ],
            },
        ],
    },
    {
        "query": "snowy mountains scheme inauguration",
        "category": "newspaper",
        "articles": [
            {
                "trove_id": "235667890",
                "trove_page_id": "21033455",
                "title": "Prime Minister Launches Snowy Scheme",
                "date": "1949-10-17",
                "source": "The Canberra Times (ACT)",
                "url": "https://nla.gov.au/nla.news-article235667890",
                "snippet": "Prime Minister Ben Chifley officially inaugurated the Snowy Mountains Hydro-Electric Scheme.",
                "full_text": (
                    "A crowd gathered at Adaminaby to witness Prime Minister Ben Chifley commence construction of "
                    "the Snowy Mountains Hydro-Electric Scheme. The project promised irrigation for inland farming "
                    "and renewable electricity for post-war industry."
                ),
                "pinned": True,
                "cards": [
                    {
                        "type": "event",
                        "title": "Snowy Scheme Inauguration",
                        "content": "Prime Minister Ben Chifley initiated the Snowy Mountains works at Adaminaby.",
                        "metadata": {"year": 1949},
                    },
                    {
                        "type": "person",
                        "title": "Ben Chifley",
                        "content": "Australian Prime Minister advocating for nation-building hydroelectric infrastructure.",
                        "metadata": {"role": "Prime Minister"},
                    },
                    {
                        "type": "place",
                        "title": "Adaminaby Ceremony Ground",
                        "content": "Site where the inaugural blasting commenced the Snowy Mountains Scheme.",
                        "metadata": {"state": "New South Wales"},
                    },
                ],
                "images": [
                    {
                        "kind": "primary",
                        "source": "National Archives of Australia",
                        "source_url": "https://example.org/images/snowy_launch.jpg",
                        "width": 1280,
                        "height": 720,
                        "metadata": {"caption": "Prime Minister Chifley at the Snowy launch ceremony."},
                    }
                ],
                "summary": "Ben Chifley opened the Snowy Mountains Scheme, promising power and irrigation for the nation.",
                "summary_bullets": [
                    "Inaugural ceremony held at Adaminaby.",
                    "Project positioned as post-war reconstruction effort.",
                ],
            },
            {
                "trove_id": "245880112",
                "trove_page_id": "21044501",
                "title": "Engineers Outline Multicultural Workforce",
                "date": "1952-06-01",
                "source": "The Sun (Sydney, NSW)",
                "url": "https://nla.gov.au/nla.news-article245880112",
                "snippet": "Snowy Mountains Authority reported on its international engineering teams and worker villages.",
                "full_text": (
                    "The Snowy Mountains Authority detailed the contributions of migrants from more than twenty nations. "
                    "New worker housing, technical colleges, and safety programs underscored the scheme's scale."
                ),
                "pinned": False,
                "cards": [
                    {
                        "type": "event",
                        "title": "Progress Report Released",
                        "content": "The Authority emphasised migrant expertise and training facilities supporting the scheme.",
                        "metadata": {"year": 1952},
                    },
                    {
                        "type": "quote",
                        "title": "Engineering Collaboration",
                        "content": "\"The Snowy is a meeting of nations in pursuit of shared prosperity.\"",
                        "metadata": {"speaker": "Snowy Mountains Authority"},
                    },
                ],
                "images": [],
                "summary": "Progress updates highlighted international labour, training, and housing supporting Snowy works.",
                "summary_bullets": [
                    "Authority credited migrant engineers.",
                    "Training colleges expanded technical capacity.",
                ],
            },
        ],
    },
]


def _build_search_payloads() -> Dict[str, Dict[str, Any]]:
    """Create mock Trove API payloads keyed by lowercase query string."""
    payloads: Dict[str, Dict[str, Any]] = {}
    for topic in SAMPLE_TOPICS:
        records = []
        for article in topic["articles"]:
            records.append(
                {
                    "id": article["trove_id"],
                    "heading": article["title"],
                    "date": article["date"],
                    "title": {"title": article["source"]},
                    "snippet": article["snippet"],
                    "trovePageUrl": f"https://nla.gov.au/nla.news-page{article['trove_page_id']}",
                    "troveUrl": article["url"],
                }
            )
        payloads[topic["query"]] = {
            "category": [
                {
                    "code": topic["category"],
                    "records": {"article": records},
                }
            ]
        }
    return payloads


class DummyTroveClient:
    """Stub async client returning curated payloads."""

    def __init__(self, payloads: Dict[str, Dict[str, Any]]):
        self.payloads = payloads

    async def search(  # type: ignore[override]
        self,
        q: str = "",
        category: str = "newspaper",
        n: int = 20,
        s: int = 0,
        **_: Any,
    ) -> Dict[str, Any]:
        key = (q or "").strip().lower()
        payload = self.payloads.get(key)
        if payload:
            return payload
        # Fallback payload merges all records for robustness.
        merged: Dict[str, Any] = {"category": []}
        for item in self.payloads.values():
            merged["category"].extend(item.get("category", []))
        return merged


def seed_articles() -> None:
    """Populate the context database with curated articles, cards, and imagery."""
    touch_session(SESSION_ID)
    for topic in SAMPLE_TOPICS:
        for article in topic["articles"]:
            base_payload = {
                "sid": SESSION_ID,
                "trove_id": article["trove_id"],
                "id": article["trove_id"],
                "title": article["title"],
                "date": article["date"],
                "source": article["source"],
                "url": article["url"],
                "snippet": article["snippet"],
            }
            upsert_item(SESSION_ID, base_payload)
            _store_rich_article_fields(
                SESSION_ID,
                article["trove_id"],
                full_text=article["full_text"],
                summary=article.get("summary"),
                summary_bullets=article.get("summary_bullets", []),
            )
            save_kingfisher_cards(article["trove_id"], article["cards"])
            if article.get("images"):
                save_article_images(article["trove_id"], article["images"])
            if article.get("pinned"):
                set_pinned(SESSION_ID, article["trove_id"], True)
    logger.info("Seeded %d articles across %d topics.", sum(len(t["articles"]) for t in SAMPLE_TOPICS), len(SAMPLE_TOPICS))


def _capture_response(response, *, expect_json: bool) -> Dict[str, Any]:
    """Normalise TestClient responses for reporting."""
    entry: Dict[str, Any] = {"status": response.status_code}
    if expect_json:
        try:
            entry["data"] = response.json()
        except ValueError:
            entry["error"] = response.text[:500]
    else:
        entry["html_length"] = len(response.text)
    if response.status_code >= 400 and "error" not in entry:
        entry["error"] = response.text[:500]
    return entry


def run_endpoint_smoke_tests() -> Dict[str, Any]:
    """Exercise key endpoints and capture their responses."""
    payloads = _build_search_payloads()
    dummy_client = DummyTroveClient(payloads)
    app.dependency_overrides[get_trove_client] = lambda: dummy_client  # type: ignore[assignment]

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            results: Dict[str, Any] = {
                "search": [],
                "articles": {},
                "brief_articles": None,
            }

            for topic in SAMPLE_TOPICS:
                resp = client.get(
                    "/search",
                    params={"q": topic["query"], "category": topic["category"], "n": 5, "s": 0},
                    headers=SESSION_HEADERS,
                )
                if resp.status_code >= 400:
                    logger.warning("Search for '%s' returned %s", topic["query"], resp.status_code)
                entry = _capture_response(resp, expect_json=False)
                entry["query"] = topic["query"]
                results["search"].append(entry)

                for article in topic["articles"]:
                    article_id = article["trove_id"]
                    article_results: Dict[str, Any] = {}

                    pin_resp = client.get(f"/pin/{article_id}", headers=SESSION_HEADERS)
                    if pin_resp.status_code >= 400:
                        logger.warning("/pin/%s returned %s", article_id, pin_resp.status_code)
                    article_results["pin"] = _capture_response(pin_resp, expect_json=True)

                    cards_resp = client.get(f"/cards/{article_id}", headers=SESSION_HEADERS)
                    if cards_resp.status_code >= 400:
                        logger.warning("/cards/%s returned %s", article_id, cards_resp.status_code)
                    article_results["cards"] = _capture_response(cards_resp, expect_json=True)

                    summary_resp = client.post(
                        f"/summarize-pin/{article_id}",
                        headers=SESSION_HEADERS,
                        params={"response_format": "json"},
                    )
                    if summary_resp.status_code >= 400:
                        logger.warning("/summarize-pin/%s returned %s", article_id, summary_resp.status_code)
                    article_results["summary"] = _capture_response(summary_resp, expect_json=True)

                    brief_resp = client.get(f"/api/brief/{article_id}", headers=SESSION_HEADERS)
                    if brief_resp.status_code >= 400:
                        logger.warning("/api/brief/%s returned %s", article_id, brief_resp.status_code)
                    article_results["brief"] = _capture_response(brief_resp, expect_json=True)

                    results["articles"][article_id] = article_results

            brief_list_resp = client.get("/api/brief/articles", headers=SESSION_HEADERS)
            if brief_list_resp.status_code >= 400:
                logger.warning("/api/brief/articles returned %s", brief_list_resp.status_code)
            results["brief_articles"] = _capture_response(brief_list_resp, expect_json=True)

            health_resp = client.get("/health")
            if health_resp.status_code >= 400:
                logger.warning("/health returned %s", health_resp.status_code)
            results["health"] = _capture_response(health_resp, expect_json=True)

            return results
    finally:
        app.dependency_overrides.pop(get_trove_client, None)


def assemble_report(endpoint_results: Dict[str, Any]) -> Dict[str, Any]:
    """Combine database state and endpoint responses into a single report."""
    stored_articles = list_articles(SESSION_ID, limit=100)
    stored_cards = {
        article["trove_id"]: list_kingfisher_cards(article["trove_id"]) for article in stored_articles
    }

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "session_id": SESSION_ID,
        "topics": [topic["query"] for topic in SAMPLE_TOPICS],
        "endpoint_results": endpoint_results,
        "stored_articles": stored_articles,
        "stored_cards": stored_cards,
    }


def write_report(report: Dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote sample brief report to %s", OUTPUT_PATH)


def main() -> None:
    logger.info("Preparing context store at %s", DB_PATH)
    _ensure_extended_schema()
    seed_articles()
    endpoint_results = run_endpoint_smoke_tests()
    report = assemble_report(endpoint_results)
    write_report(report)
    logger.info("Sample research seeding complete.")


if __name__ == "__main__":
    main()


