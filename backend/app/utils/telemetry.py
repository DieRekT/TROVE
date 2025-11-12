"""Telemetry logging for deep research runs."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TELEMETRY_FILE = Path("outputs/research_telemetry.jsonl")


def log_research_run(
    query: str,
    years_from: Optional[int],
    years_to: Optional[int],
    max_sources: int,
    depth: str,
    sources_count: int,
    findings_count: int,
    timeline_count: int,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Log a deep research run to telemetry file."""
    try:
        TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "query": query,
            "years_from": years_from,
            "years_to": years_to,
            "max_sources": max_sources,
            "depth": depth,
            "sources_count": sources_count,
            "findings_count": findings_count,
            "timeline_count": timeline_count,
            "success": success,
            "error": error,
        }
        
        with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log research telemetry: {e}")


def get_research_stats(days: int = 7) -> Dict[str, any]:
    """Get research statistics for the last N days."""
    if not TELEMETRY_FILE.exists():
        return {
            "total": 0,
            "today": 0,
            "last_7d": 0,
            "last_run": None,
            "recent_runs": [],
        }
    
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        total = 0
        today_count = 0
        last_7d_count = 0
        last_run: Optional[str] = None
        recent_runs: List[Dict] = []
        
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    total += 1
                    ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                    ts_utc = ts.replace(tzinfo=None)
                    
                    if ts_utc >= today_start:
                        today_count += 1
                    if ts_utc >= seven_days_ago:
                        last_7d_count += 1
                    
                    if not last_run or ts_utc > datetime.fromisoformat(last_run.replace("Z", "+00:00")).replace(tzinfo=None):
                        last_run = entry["timestamp"]
                    
                    if ts_utc >= cutoff:
                        recent_runs.append(entry)
                except Exception:
                    continue
        
        # Sort recent runs by timestamp (newest first)
        recent_runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {
            "total": total,
            "today": today_count,
            "last_7d": last_7d_count,
            "last_run": last_run,
            "recent_runs": recent_runs[:10],  # Last 10 runs
        }
    except Exception as e:
        logger.warning(f"Failed to read research telemetry: {e}")
        return {
            "total": 0,
            "today": 0,
            "last_7d": 0,
            "last_run": None,
            "recent_runs": [],
        }

