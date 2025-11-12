"""SQLite store for research jobs and evidence."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.research.schemas import Evidence, Job

DB_PATH = Path("data/research.db")
OUTPUTS_DIR = Path("outputs/research")


def _ensure_dirs():
    """Ensure database and output directories exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """Get database connection with schema initialized."""
    _ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Create tables if they don't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS research_jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            progress_pct INTEGER DEFAULT 0,
            summary_path TEXT,
            evidence_path TEXT,
            question TEXT,
            error_message TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS research_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            published_at TEXT,
            snippet TEXT,
            quotes TEXT,
            score REAL DEFAULT 0.0,
            rationale TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES research_jobs(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS web_cache (
            url TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )
    """)

    conn.commit()
    return conn


def create_job(question: str, region: Optional[str] = None, time_window: Optional[str] = None) -> str:
    """Create a new research job and return its ID."""
    import uuid
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO research_jobs (id, status, created_at, updated_at, question)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, "queued", now, now, question),
    )
    conn.commit()
    conn.close()

    # Create output directory
    job_dir = OUTPUTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    return job_id


def update_job_status(
    job_id: str,
    status: Optional[str] = None,
    progress_pct: Optional[int] = None,
    summary_path: Optional[str] = None,
    evidence_path: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Update job status and metadata."""
    conn = _get_conn()
    updates = []
    params = []

    if status:
        updates.append("status = ?")
        params.append(status)
    if progress_pct is not None:
        updates.append("progress_pct = ?")
        params.append(progress_pct)
    if summary_path:
        updates.append("summary_path = ?")
        params.append(summary_path)
    if evidence_path:
        updates.append("evidence_path = ?")
        params.append(evidence_path)
    if error_message:
        updates.append("error_message = ?")
        params.append(error_message)

    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(job_id)

    if updates:
        query = f"UPDATE research_jobs SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        conn.commit()
    conn.close()


def append_evidence(job_id: str, evidence: Evidence):
    """Append evidence to a job."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO research_evidence 
        (job_id, title, url, source, published_at, snippet, quotes, score, rationale, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            evidence.title,
            evidence.url,
            evidence.source,
            evidence.published_at,
            evidence.snippet,
            json.dumps(evidence.quotes),
            evidence.score,
            evidence.rationale,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def load_job(job_id: str) -> Optional[Job]:
    """Load a job by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM research_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    if not row:
        return None

    return Job(
        id=row["id"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        progress_pct=row["progress_pct"],
        summary_path=row["summary_path"],
        evidence_path=row["evidence_path"],
        question=row["question"] or "",
        error_message=row["error_message"],
    )


def list_evidence(job_id: str) -> List[Evidence]:
    """List all evidence for a job."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM research_evidence WHERE job_id = ? ORDER BY score DESC, created_at",
        (job_id,),
    ).fetchall()
    conn.close()

    return [
        Evidence(
            title=row["title"],
            url=row["url"],
            source=row["source"],
            published_at=row["published_at"],
            snippet=row["snippet"],
            quotes=json.loads(row["quotes"] or "[]"),
            score=row["score"],
            rationale=row["rationale"],
        )
        for row in rows
    ]


def persist_report(job_id: str, markdown: str) -> str:
    """Persist markdown report to disk and return path."""
    job_dir = OUTPUTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    report_path = job_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    return str(report_path)


def get_report_path(job_id: str) -> Path:
    """Get the report file path for a job."""
    return OUTPUTS_DIR / job_id / "report.md"


def cache_web_content(url: str, content: str):
    """Cache web page content."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO web_cache (url, content, cached_at) VALUES (?, ?, ?)",
        (url, content, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_cached_web_content(url: str) -> Optional[str]:
    """Get cached web content if available."""
    conn = _get_conn()
    row = conn.execute("SELECT content FROM web_cache WHERE url = ?", (url,)).fetchone()
    conn.close()
    return row["content"] if row else None


def list_recent_jobs(limit: int = 5) -> List[Job]:
    """List recent research jobs."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM research_jobs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    return [
        Job(
            id=row["id"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            progress_pct=row["progress_pct"],
            summary_path=row["summary_path"],
            evidence_path=row["evidence_path"],
            question=row["question"] or "",
            error_message=row["error_message"],
        )
        for row in rows
    ]

