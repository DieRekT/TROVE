from __future__ import annotations
import sqlite3
import os
import json
import time
import threading
from contextlib import contextmanager

DB_PATH = os.environ.get("TROVEING_DB", os.path.join(os.getcwd(), "troveing.sqlite"))


def _init(conn: sqlite3.Connection):
    c = conn.cursor()
    c.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS jobs(
      id TEXT PRIMARY KEY,
      query TEXT NOT NULL,
      years_from INT, years_to INT, max_pages INT,
      state TEXT,              -- "New South Wales" or "Western Australia"
      status TEXT NOT NULL,    -- queued|running|done|error
      progress REAL DEFAULT 0, -- 0..1
      created_at REAL, updated_at REAL,
      error TEXT
    );
    CREATE TABLE IF NOT EXISTS sources(
      id TEXT PRIMARY KEY,     -- e.g. TROVE:articleId
      raw JSON NOT NULL,
      title TEXT, year INT, url TEXT,
      text TEXT,               -- fulltext or snippet
      dataset TEXT NOT NULL DEFAULT 'TROVE'
    );
    -- FTS for searching/snippets (non-contentless for easier management)
    CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
      id UNINDEXED, title, text
    );
    """)
    conn.commit()


@contextmanager
def get_conn():
    need = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if need:
        _init(conn)
    yield conn
    conn.commit()
    conn.close()


def upsert_source(conn, sid: str, title: str, year, url: str, text: str, raw: dict):
    c = conn.cursor()
    # First, insert/update the source
    c.execute(
        "INSERT OR REPLACE INTO sources(id, raw, title, year, url, text, dataset) VALUES(?,?,?,?,?,?, 'TROVE')",
        (sid, json.dumps(raw, ensure_ascii=False), title, year, url, text)
    )
    # Update FTS index (delete old entry, insert new)
    c.execute("DELETE FROM sources_fts WHERE id=?", (sid,))
    c.execute(
        "INSERT INTO sources_fts(id, title, text) VALUES(?,?,?)",
        (sid, title or '', text or '')
    )
    conn.commit()

