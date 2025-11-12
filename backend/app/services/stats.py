from __future__ import annotations
from datetime import datetime, timezone, timedelta
from ..db import get_conn


class StatsService:
    @staticmethod
    async def compute() -> dict:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        
        try:
            with get_conn() as conn:
                # Count sources
                total_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] or 0
                
                # Count jobs (reports)
                total_reports = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='done'").fetchone()[0] or 0
                
                # Reports today
                reports_today = conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status='done' AND created_at >= ?",
                    (today_start.timestamp(),)
                ).fetchone()[0] or 0
                
                # Reports in last 7 days
                reports_7d = conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status='done' AND created_at >= ?",
                    (week_start.timestamp(),)
                ).fetchone()[0] or 0
                
                # Searches are tracked via /search endpoint calls (not stored in DB yet)
                # For now, return 0; can be enhanced with a search_log table later
                searches_today = 0
                searches_7d = 0
        except Exception:
            # Graceful degradation if DB is empty or not initialized
            total_sources = 0
            total_reports = 0
            reports_today = 0
            reports_7d = 0
            searches_today = 0
            searches_7d = 0
        
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "searches_today": searches_today,
            "searches_7d": searches_7d,
            "reports_today": reports_today,
            "reports_7d": reports_7d,
            "total_sources": total_sources,
            "total_reports": total_reports,
        }

