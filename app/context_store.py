"""SQLite-based persistent research context store with pinning and prompt packing."""

import os
import sqlite3
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple

# Configuration
DB_PATH = os.environ.get("CONTEXT_DB", os.path.join(os.path.dirname(__file__), "data", "context.db"))
MAX_PER_SESSION = int(os.environ.get("CONTEXT_MAX_PER_SESSION", "50"))


def _connect() -> sqlite3.Connection:
    """Create database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    """Initialize database schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions(
        sid TEXT PRIMARY KEY,
        created_at REAL NOT NULL,
        last_seen REAL NOT NULL
    );
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS articles(
        sid TEXT NOT NULL,
        trove_id TEXT NOT NULL,
        title TEXT,
        date TEXT,
        source TEXT,
        url TEXT,
        snippet TEXT,
        pinned INTEGER NOT NULL DEFAULT 0,
        views INTEGER NOT NULL DEFAULT 0,
        first_seen REAL NOT NULL,
        last_seen REAL NOT NULL,
        PRIMARY KEY (sid, trove_id)
    );
    """)
    
    conn.commit()
    conn.close()


def _now() -> float:
    """Get current timestamp."""
    return time.time()


def touch_session(sid: str) -> None:
    """Update session last_seen timestamp."""
    ensure_db()
    with _connect() as c:
        c.execute(
            "INSERT INTO sessions(sid, created_at, last_seen) VALUES(?,?,?) "
            "ON CONFLICT(sid) DO UPDATE SET last_seen=excluded.last_seen;",
            (sid, _now(), _now())
        )


def upsert_item(sid: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add or update an article in context.
    
    item requires at least: id (or trove_id), title, date, source, url, snippet (best-effort).
    """
    ensure_db()
    touch_session(sid)
    
    trove_id = str(item.get("trove_id") or item.get("id") or "")
    if not trove_id:
        raise ValueError("upsert_item requires id or trove_id")
    
    fields = {
        "title": (item.get("title") or item.get("heading") or "").strip(),
        "date": (item.get("date") or item.get("issued") or "").strip(),
        "source": (item.get("source") or item.get("publisher_or_source") or "").strip(),
        "url": (item.get("url") or item.get("trove_url") or "").strip(),
        "snippet": (item.get("snippet") or item.get("summary") or item.get("text", "")[:500]).strip(),
    }
    
    with _connect() as c:
        c.execute("""
        INSERT INTO articles(sid, trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen)
        VALUES(?,?,?,?,?,?,?,?,?, ?, ?)
        ON CONFLICT(sid, trove_id) DO UPDATE SET
            title=excluded.title,
            date=excluded.date,
            source=excluded.source,
            url=excluded.url,
            snippet=CASE WHEN length(excluded.snippet)>length(articles.snippet) THEN excluded.snippet ELSE articles.snippet END,
            views=articles.views+1,
            last_seen=excluded.last_seen;
        """, (
            sid, trove_id, fields["title"], fields["date"], fields["source"], 
            fields["url"], fields["snippet"], 0, 1, _now(), _now()
        ))
        
        # Enforce cap (keep pinned first, then most-recent)
        cur = c.execute("""
            SELECT trove_id, pinned FROM articles WHERE sid=? 
            ORDER BY pinned DESC, last_seen DESC
        """, (sid,))
        rows = cur.fetchall()
        if len(rows) > MAX_PER_SESSION:
            to_drop = rows[MAX_PER_SESSION:]
            for r in to_drop:
                c.execute("DELETE FROM articles WHERE sid=? AND trove_id=?", (sid, r["trove_id"]))
    
    return {"ok": True, "sid": sid, "trove_id": trove_id}


def set_pinned(sid: str, trove_id: str, pinned: bool) -> None:
    """Pin or unpin an article."""
    ensure_db()
    touch_session(sid)
    with _connect() as c:
        c.execute(
            "UPDATE articles SET pinned=? WHERE sid=? AND trove_id=?",
            (1 if pinned else 0, sid, trove_id)
        )


def clear_session(sid: str) -> None:
    """Clear all articles for a session."""
    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM articles WHERE sid=?", (sid,))
        c.execute("DELETE FROM sessions WHERE sid=?", (sid,))


def list_articles(sid: str, limit: int = MAX_PER_SESSION) -> List[Dict[str, Any]]:
    """List articles for a session, ordered by pinned then last_seen."""
    ensure_db()
    touch_session(sid)
    with _connect() as c:
        cur = c.execute("""
        SELECT trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen
        FROM articles WHERE sid=? ORDER BY pinned DESC, last_seen DESC LIMIT ?;
        """, (sid, limit))
        return [dict(r) for r in cur.fetchall()]


def pack_for_prompt(sid: str, max_chars: int = 3500) -> Dict[str, Any]:
    """
    Compose a compact, ordered bibliography-like pack for LLM prompts.
    Priority: pinned first (newest), then recent.
    Returns dict with 'text' and 'count'.
    """
    items = list_articles(sid, MAX_PER_SESSION)
    lines = []
    used = 0
    
    for it in items:
        title = it.get("title") or "Untitled"
        date = (it.get("date") or "").strip()
        source = (it.get("source") or "").strip()
        url = (it.get("url") or "").strip()
        snip = (it.get("snippet") or "").strip().replace("\n", " ")
        
        line = (
            f"- {title} ({date}, {source}). "
            f"{('Snippet: ' + snip) if snip else ''} "
            f"{('[URL: ' + url + ']') if url else ''}"
        ).strip()
        
        # Conservative char budget
        if len("\n".join(lines + [line])) > max_chars:
            break
        
        lines.append(line)
        used += 1
    
    text = "Research Context:\n" + ("\n".join(lines) if lines else "(none)")
    return {"text": text, "count": used}


def sid_from(request_headers: Dict[str, str], ip: str, ua: str) -> str:
    """Deterministic, cookie-free session id (works behind localhost/dev)."""
    sid = request_headers.get("X-Session-Id") or request_headers.get("x-session-id")
    if sid:
        return sid.strip()
    base = f"{ip}|{ua}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

