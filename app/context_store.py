"""SQLite-based persistent research context store with pinning and prompt packing."""

import os
import sqlite3
import time
import hashlib
import uuid
import json
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
        full_text TEXT,
        summary TEXT,
        summary_bullets TEXT,
        pinned INTEGER NOT NULL DEFAULT 0,
        views INTEGER NOT NULL DEFAULT 0,
        first_seen REAL NOT NULL,
        last_seen REAL NOT NULL,
        PRIMARY KEY (sid, trove_id)
    );
    """)
    
    # Add missing columns if they don't exist (for existing databases)
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN full_text TEXT;")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN summary TEXT;")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        cur.execute("ALTER TABLE articles ADD COLUMN summary_bullets TEXT;")
    except sqlite3.OperationalError:
        pass  # Column already exists

    cur.execute("""
    CREATE TABLE IF NOT EXISTS collections(
        id TEXT PRIMARY KEY,
        sid TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        color TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        FOREIGN KEY (sid) REFERENCES sessions(sid)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS collection_items(
        collection_id TEXT NOT NULL,
        trove_id TEXT NOT NULL,
        payload TEXT,
        added_at REAL NOT NULL,
        PRIMARY KEY (collection_id, trove_id),
        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes(
        id TEXT PRIMARY KEY,
        sid TEXT NOT NULL,
        article_id TEXT NOT NULL,
        note_type TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY (sid) REFERENCES sessions(sid)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lesson_cards(
        id TEXT PRIMARY KEY,
        sid TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        content TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        FOREIGN KEY (sid) REFERENCES sessions(sid)
    );
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kingfisher_cards(
        id TEXT PRIMARY KEY,
        article_id TEXT NOT NULL,
        card_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        metadata TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    """)
    
    cur.execute("""
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


def clear_tracked_only(sid: str) -> None:
    """Clear only tracked (non-pinned) articles, keeping pinned articles."""
    ensure_db()
    touch_session(sid)
    with _connect() as c:
        c.execute("DELETE FROM articles WHERE sid=? AND pinned=0", (sid,))


def _parse_summary_bullets(bullets_str: Optional[str]) -> List[str]:
    """Parse summary bullets from JSON string or return empty list."""
    if not bullets_str:
        return []
    try:
        parsed = json.loads(bullets_str) if isinstance(bullets_str, str) else bullets_str
        if isinstance(parsed, list):
            return [str(b) for b in parsed]
        return []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def list_articles(sid: str, limit: int = MAX_PER_SESSION) -> List[Dict[str, Any]]:
    """List articles for a session, ordered by pinned then last_seen."""
    ensure_db()
    touch_session(sid)
    with _connect() as c:
        # Try to include summary fields if they exist, fallback to basic fields
        try:
            cur = c.execute("""
                SELECT trove_id, title, date, source, url, snippet, full_text, summary, summary_bullets, pinned, views, first_seen, last_seen
                FROM articles WHERE sid=? ORDER BY pinned DESC, last_seen DESC LIMIT ?;
            """, (sid, limit))
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                if "summary_bullets" in row:
                    row["summary_bullets"] = _parse_summary_bullets(row.get("summary_bullets"))
            return rows
        except sqlite3.OperationalError:
            # Fallback if summary columns don't exist
            cur = c.execute("""
                SELECT trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen
                FROM articles WHERE sid=? ORDER BY pinned DESC, last_seen DESC LIMIT ?;
            """, (sid, limit))
            return [dict(r) for r in cur.fetchall()]


def list_recent_articles(limit: int = 30, sid: Optional[str] = None, order_by: str = "last_seen DESC") -> List[Dict[str, Any]]:
    """List recent articles, optionally filtered by session. Orders by last_seen DESC by default."""
    # Validate order_by to prevent SQL injection - only allow safe column names and ASC/DESC
    allowed_columns = {"trove_id", "title", "date", "source", "last_seen", "first_seen", "pinned", "views"}
    order_parts = order_by.strip().upper().split()
    if len(order_parts) == 0:
        order_by = "last_seen DESC"
    elif len(order_parts) == 1:
        col = order_parts[0]
        if col not in allowed_columns:
            order_by = "last_seen DESC"
        else:
            order_by = f"{col} DESC"
    elif len(order_parts) == 2:
        col, direction = order_parts[0], order_parts[1]
        if col not in allowed_columns or direction not in {"ASC", "DESC"}:
            order_by = "last_seen DESC"
        else:
            order_by = f"{col} {direction}"
    else:
        order_by = "last_seen DESC"
    
    ensure_db()
    with _connect() as c:
        # Try to include summary fields if they exist
        try:
            if sid:
                cur = c.execute(f"""
                SELECT trove_id, title, date, source, url, snippet, full_text, summary, summary_bullets, pinned, views, first_seen, last_seen
                FROM articles WHERE sid=? ORDER BY {order_by} LIMIT ?;
                """, (sid, limit))
            else:
                cur = c.execute(f"""
                SELECT trove_id, title, date, source, url, snippet, full_text, summary, summary_bullets, pinned, views, first_seen, last_seen
                FROM articles ORDER BY {order_by} LIMIT ?;
                """, (limit,))
        except sqlite3.OperationalError:
            # Fallback if summary columns don't exist
            if sid:
                cur = c.execute(f"""
                SELECT trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen
                FROM articles WHERE sid=? ORDER BY {order_by} LIMIT ?;
                """, (sid, limit))
            else:
                cur = c.execute(f"""
                SELECT trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen
                FROM articles ORDER BY {order_by} LIMIT ?;
                """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            if "summary_bullets" in row:
                row["summary_bullets"] = _parse_summary_bullets(row.get("summary_bullets"))
        return rows


def move_pinned_article(sid: str, trove_id: str, direction: str) -> bool:
    """
    Move a pinned article up or down by swapping its last_seen value with a neighbour.
    Returns True if the article was moved, False otherwise.
    """
    if direction not in {"up", "down"}:
        raise ValueError("direction must be 'up' or 'down'")

    ensure_db()
    touch_session(sid)

    with _connect() as c:
        cur = c.execute("""
            SELECT trove_id, last_seen
            FROM articles
            WHERE sid=? AND pinned=1
            ORDER BY last_seen DESC
        """, (sid,))
        rows = cur.fetchall()

        if not rows:
            return False

        # Find current article index
        current_idx = None
        for idx, row in enumerate(rows):
            if row["trove_id"] == trove_id:
                current_idx = idx
                break

        if current_idx is None:
            return False

        # Determine target index
        if direction == "up" and current_idx > 0:
            target_idx = current_idx - 1
        elif direction == "down" and current_idx < len(rows) - 1:
            target_idx = current_idx + 1
        else:
            return False

        # Swap last_seen values
        current_ts = rows[current_idx]["last_seen"]
        target_ts = rows[target_idx]["last_seen"]

        c.execute("""
            UPDATE articles SET last_seen=? WHERE sid=? AND trove_id=?
        """, (target_ts, sid, trove_id))

        c.execute("""
            UPDATE articles SET last_seen=? WHERE sid=? AND trove_id=?
        """, (current_ts, sid, rows[target_idx]["trove_id"]))

        return True


def save_kingfisher_cards(article_id: str, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Persist a set of Kingfisher cards for a Trove article."""
    if not article_id:
        raise ValueError("article_id is required to store Kingfisher cards")

    ensure_db()
    stored: List[Dict[str, Any]] = []
    now = _now()

    with _connect() as c:
        c.execute("DELETE FROM kingfisher_cards WHERE article_id=?", (article_id,))

        for card in cards:
            data = dict(card or {})
            card_type = str(data.get("type") or data.get("card_type") or "note").strip() or "note"
            title = (data.get("title") or "").strip()
            content = (data.get("content") or "").strip()
            metadata = data.get("metadata") or {}

            card_id = str(data.get("id") or uuid.uuid4())
            try:
                metadata_json = json.dumps(metadata, ensure_ascii=False)
            except (TypeError, ValueError):
                metadata_json = json.dumps({})

            c.execute(
                """
                INSERT INTO kingfisher_cards(id, article_id, card_type, title, content, metadata, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    card_id,
                    article_id,
                    card_type,
                    title,
                    content,
                    metadata_json,
                    now,
                    now,
                ),
            )

            stored.append(
                {
                    "id": card_id,
                    "article_id": article_id,
                    "type": card_type,
                    "title": title,
                    "content": content,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return stored


def list_kingfisher_cards(article_id: str) -> List[Dict[str, Any]]:
    """Return stored Kingfisher cards for an article."""
    if not article_id:
        return []

    ensure_db()
    with _connect() as c:
        cur = c.execute(
            """
            SELECT id, article_id, card_type, title, content, metadata, created_at, updated_at
            FROM kingfisher_cards
            WHERE article_id=?
            ORDER BY created_at ASC, id ASC
            """,
            (article_id,),
        )
        rows = []
        for row in cur.fetchall():
            metadata_raw = row["metadata"]
            try:
                metadata = json.loads(metadata_raw) if metadata_raw else {}
                if not isinstance(metadata, dict):
                    metadata = {}
            except (TypeError, json.JSONDecodeError, ValueError):
                metadata = {}
            rows.append(
                {
                    "id": row["id"],
                    "article_id": row["article_id"],
                    "type": row["card_type"],
                    "title": row["title"] or "",
                    "content": row["content"] or "",
                    "metadata": metadata,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return rows


def delete_kingfisher_cards(article_id: str) -> None:
    """Remove stored Kingfisher cards for an article."""
    if not article_id:
        return

    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM kingfisher_cards WHERE article_id=?", (article_id,))


def save_article_images(article_id: str, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Persist image metadata for a Trove article."""
    if not article_id:
        raise ValueError("article_id is required to store images")

    ensure_db()
    stored: List[Dict[str, Any]] = []
    now = _now()

    with _connect() as c:
        c.execute("DELETE FROM article_images WHERE article_id=?", (article_id,))

        for image in images or []:
            data = dict(image or {})
            image_id = str(data.get("id") or uuid.uuid4())
            kind = (data.get("kind") or data.get("type") or "primary")
            kind = str(kind).strip() or "primary"
            source = (data.get("source") or "").strip()
            source_url = (data.get("source_url") or data.get("url") or "").strip()
            local_path = (data.get("local_path") or data.get("path") or "").strip()

            def _as_int(value: Any) -> Optional[int]:
                try:
                    return int(value) if value is not None and str(value).strip() != "" else None
                except (TypeError, ValueError):
                    return None

            width = _as_int(data.get("width"))
            height = _as_int(data.get("height"))

            generated_flag = data.get("generated")
            if isinstance(generated_flag, str):
                generated = 1 if generated_flag.lower() in {"true", "1", "yes", "y"} else 0
            else:
                generated = 1 if bool(generated_flag) else 0

            metadata = data.get("metadata") or {}
            try:
                metadata_json = json.dumps(metadata, ensure_ascii=False)
            except (TypeError, ValueError):
                metadata_json = json.dumps({})
                metadata = {}

            c.execute(
                """
                INSERT INTO article_images(
                    id, article_id, kind, source, source_url, local_path,
                    width, height, generated, metadata, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    image_id,
                    article_id,
                    kind,
                    source,
                    source_url,
                    local_path,
                    width,
                    height,
                    generated,
                    metadata_json,
                    now,
                    now,
                ),
            )

            stored.append(
                {
                    "id": image_id,
                    "article_id": article_id,
                    "kind": kind,
                    "source": source,
                    "source_url": source_url,
                    "local_path": local_path,
                    "width": width,
                    "height": height,
                    "generated": bool(generated),
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return stored


def list_article_images(article_id: str, include_generated: bool = True) -> List[Dict[str, Any]]:
    """Return stored images for an article."""
    if not article_id:
        return []

    ensure_db()
    with _connect() as c:
        query = """
            SELECT id, article_id, kind, source, source_url, local_path,
                   width, height, generated, metadata, created_at, updated_at
            FROM article_images
            WHERE article_id=?
            ORDER BY generated ASC, created_at ASC, id ASC
        """
        params: Tuple[Any, ...] = (article_id,)

        if not include_generated:
            query = query.replace("WHERE", "WHERE generated=0 AND", 1)

        cur = c.execute(query, params)
        rows = []
        for row in cur.fetchall():
            metadata_raw = row["metadata"]
            try:
                metadata = json.loads(metadata_raw) if metadata_raw else {}
                if not isinstance(metadata, dict):
                    metadata = {}
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}

            rows.append(
                {
                    "id": row["id"],
                    "article_id": row["article_id"],
                    "kind": row["kind"],
                    "source": row["source"],
                    "source_url": row["source_url"],
                    "local_path": row["local_path"],
                    "width": row["width"],
                    "height": row["height"],
                    "generated": bool(row["generated"]),
                    "metadata": metadata,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return rows


def delete_article_images(article_id: str) -> None:
    """Remove stored images for an article."""
    if not article_id:
        return

    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM article_images WHERE article_id=?", (article_id,))


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
    """Generate deterministic session ID from headers, IP, and user agent."""
    raw = json.dumps({"headers": request_headers, "ip": ip, "ua": ua}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# -----------------
# Collections API
# -----------------


def list_collections(sid: str) -> List[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT id, sid, name, description, color, created_at, updated_at FROM collections WHERE sid=? ORDER BY created_at DESC",
            (sid,)
        )
        return [dict(row) for row in cur.fetchall()]


def get_or_create_default_collection(sid: str) -> Dict[str, Any]:
    """Get the first collection for a session, or create a default one if none exists."""
    ensure_db()
    collections = list_collections(sid)
    if collections:
        return collections[0]  # Return the first (most recent) collection
    
    # Create a default collection
    result = create_collection(sid, "My Collection", "Default collection for saved items")
    return result["collection"]


def get_collection(collection_id: str) -> Optional[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT id, sid, name, description, color, created_at, updated_at FROM collections WHERE id=?",
            (collection_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_collection(sid: str, name: str, description: str = "", color: str = "#3b82f6") -> Dict[str, Any]:
    ensure_db()
    touch_session(sid)
    collection_id = str(uuid.uuid4())
    now = _now()
    with _connect() as c:
        c.execute(
            """
            INSERT INTO collections(id, sid, name, description, color, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (collection_id, sid, name.strip() or "Untitled Collection", description.strip(), color, now, now)
        )
    return {
        "ok": True,
        "collection": get_collection(collection_id)
    }


def update_collection(collection_id: str, name: Optional[str] = None, description: Optional[str] = None, color: Optional[str] = None) -> None:
    ensure_db()
    updates = []
    params: List[Any] = []
    if name is not None:
        updates.append("name=?")
        params.append(name.strip())
    if description is not None:
        updates.append("description=?")
        params.append(description.strip())
    if color is not None:
        updates.append("color=?")
        params.append(color)
    if not updates:
        return
    updates.append("updated_at=?")
    params.append(_now())
    params.append(collection_id)
    with _connect() as c:
        c.execute(f"UPDATE collections SET {', '.join(updates)} WHERE id=?", params)


def delete_collection(collection_id: str) -> None:
    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM collection_items WHERE collection_id=?", (collection_id,))
        c.execute("DELETE FROM collections WHERE id=?", (collection_id,))


def add_item_to_collection(collection_id: str, trove_id: str, notes: str = "") -> Dict[str, Any]:
    ensure_db()
    if not trove_id:
        raise ValueError("trove_id required")
    payload = json.dumps({"notes": notes.strip()}) if notes else None
    with _connect() as c:
        c.execute(
            """
            INSERT INTO collection_items(collection_id, trove_id, payload, added_at)
            VALUES(?,?,?,?)
            ON CONFLICT(collection_id, trove_id) DO UPDATE SET payload=excluded.payload, added_at=excluded.added_at
            """,
            (collection_id, trove_id.strip(), payload, _now())
        )
    return {"ok": True}


def remove_item_from_collection(collection_id: str, trove_id: str) -> None:
    ensure_db()
    with _connect() as c:
        c.execute(
            "DELETE FROM collection_items WHERE collection_id=? AND trove_id=?",
            (collection_id, trove_id)
        )


def get_collection_items(collection_id: str) -> List[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT trove_id, payload, added_at FROM collection_items WHERE collection_id=? ORDER BY added_at DESC",
            (collection_id,)
        )
        items = []
        for row in cur.fetchall():
            notes = ""
            if row["payload"]:
                try:
                    payload = json.loads(row["payload"])
                    notes = payload.get("notes", "")
                except json.JSONDecodeError:
                    notes = ""
            items.append({
                "trove_id": row["trove_id"],
                "notes": notes,
                "added_at": row["added_at"]
            })
        return items


# -----------------
# Notes API
# -----------------


def add_note(sid: str, article_id: str, text: str, note_type: str = "note") -> Dict[str, Any]:
    ensure_db()
    touch_session(sid)
    note_id = str(uuid.uuid4())
    with _connect() as c:
        c.execute(
            """
            INSERT INTO notes(id, sid, article_id, note_type, text, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (note_id, sid, article_id, note_type, text.strip(), _now())
        )
    return {"ok": True, "note_id": note_id}


def get_notes_for_article(sid: str, article_id: str) -> List[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT id, note_type, text, created_at FROM notes WHERE sid=? AND article_id=? ORDER BY created_at DESC",
            (sid, article_id)
        )
        return [dict(row) for row in cur.fetchall()]


def delete_note(sid: str, note_id: str) -> None:
    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM notes WHERE sid=? AND id=?", (sid, note_id))


# -----------------
# Pinned helpers
# -----------------


def list_pinned_articles(sid: str, limit: int = 20) -> List[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            """
            SELECT trove_id, title, date, source, url, snippet, pinned, views, first_seen, last_seen
            FROM articles
            WHERE sid=? AND pinned=1
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (sid, limit)
        )
        return [dict(row) for row in cur.fetchall()]


# -----------------
# Lesson cards
# -----------------


def list_lesson_cards(sid: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        if category:
            cur = c.execute(
                "SELECT id, sid, title, category, content, created_at, updated_at FROM lesson_cards WHERE sid=? AND category=? ORDER BY updated_at DESC",
                (sid, category)
            )
        else:
            cur = c.execute(
                "SELECT id, sid, title, category, content, created_at, updated_at FROM lesson_cards WHERE sid=? ORDER BY updated_at DESC",
                (sid,)
            )
        cards = []
        for row in cur.fetchall():
            payload = {"front_text": "", "back_text": "", "tags": []}
            if row["content"]:
                try:
                    payload.update(json.loads(row["content"]))
                except json.JSONDecodeError:
                    pass
            cards.append({
                "id": row["id"],
                "sid": row["sid"],
                "title": row["title"],
                "category": row["category"],
                "front_text": payload.get("front_text", ""),
                "back_text": payload.get("back_text", ""),
                "tags": payload.get("tags", []),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        return cards


def create_lesson_card(
    sid: str,
    title: str,
    front_text: str,
    back_text: str,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    ensure_db()
    touch_session(sid)
    card_id = str(uuid.uuid4())
    now = _now()
    content = {
        "front_text": front_text or "",
        "back_text": back_text or "",
        "tags": tags or [],
    }
    with _connect() as c:
        c.execute(
            """
            INSERT INTO lesson_cards(id, sid, title, category, content, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (card_id, sid, title.strip() or "Untitled Card", category, json.dumps(content), now, now)
        )
    card = get_lesson_card(card_id)
    return card if card else {}


def get_lesson_card(card_id: str) -> Optional[Dict[str, Any]]:
    ensure_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT id, sid, title, category, content, created_at, updated_at FROM lesson_cards WHERE id=?",
            (card_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = {"front_text": "", "back_text": "", "tags": []}
        if row["content"]:
            try:
                payload.update(json.loads(row["content"]))
            except json.JSONDecodeError:
                pass
        return {
            "id": row["id"],
            "sid": row["sid"],
            "title": row["title"],
            "category": row["category"],
            "front_text": payload.get("front_text", ""),
            "back_text": payload.get("back_text", ""),
            "tags": payload.get("tags", []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def update_lesson_card(
    card_id: str,
    title: Optional[str] = None,
    front_text: Optional[str] = None,
    back_text: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> None:
    ensure_db()
    updates = []
    params: List[Any] = []
    if title is not None:
        updates.append("title=?")
        params.append(title.strip())
    if category is not None:
        updates.append("category=?")
        params.append(category)
    if any(v is not None for v in (front_text, back_text, tags)):
        card = get_lesson_card(card_id) or {}
        content = {
            "front_text": front_text if front_text is not None else card.get("front_text", ""),
            "back_text": back_text if back_text is not None else card.get("back_text", ""),
            "tags": tags if tags is not None else card.get("tags", []),
        }
        updates.append("content=?")
        params.append(json.dumps(content))
    if not updates:
        return
    updates.append("updated_at=?")
    params.append(_now())
    params.append(card_id)
    with _connect() as c:
        c.execute(f"UPDATE lesson_cards SET {', '.join(updates)} WHERE id=?", params)


def delete_lesson_card(card_id: str) -> None:
    ensure_db()
    with _connect() as c:
        c.execute("DELETE FROM lesson_cards WHERE id=?", (card_id,))

