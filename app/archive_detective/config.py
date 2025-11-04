from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root: ~/Projects/trove/
# This file lives at .../app/archive_detective/config.py → parents[2] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env file to ensure environment variables are available
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


ARCHIVE_DETECTIVE_ENABLED = _env_bool("ARCHIVE_DETECTIVE_ENABLED", True)
APP_TITLE = os.getenv("APP_TITLE", "Archive Detective — Land stories in minutes")

DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
QUERIES_DIR = Path(os.getenv("QUERIES_DIR", PROJECT_ROOT / "queries"))
DOCS_DIR = Path(os.getenv("DOCS_DIR", PROJECT_ROOT / "docs"))
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", PROJECT_ROOT / "outputs"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# AI Cost Guardrails (prep for Phase B)
AI_ENABLED = _env_bool("AI_ENABLED", False)
AI_MAX_CALLS_PER_MIN = int(os.getenv("AI_MAX_CALLS_PER_MIN", "10"))
AI_DAILY_USD_LIMIT = float(os.getenv("AI_DAILY_USD_LIMIT", "0.50"))
AI_MODEL_ROUTER = os.getenv("AI_MODEL_ROUTER", "gpt-4o-mini")
ENHANCE_QUERIES = _env_bool("ENHANCE_QUERIES", False)


def ensure_dirs() -> None:
    for p in (DATA_DIR, QUERIES_DIR, DOCS_DIR, OUTPUTS_DIR):
        p.mkdir(parents=True, exist_ok=True)
    # Ensure images subdirectory exists
    (OUTPUTS_DIR / "images").mkdir(parents=True, exist_ok=True)


PROPERTY_SEED_PATH = DATA_DIR / "property.json"
DEFAULT_PROPERTY = {
    "address": "12A Clarence Street, Ashby NSW 2463",
    "alias": "Moongi Cottage",
    "legal": {"lot": "1", "plan_type": "DP", "plan_number": "586103", "formatted": "1/586103"},
    "parish": "Ashby",
    "county": "Clarence",
    "state": "NSW",
    "country": "Australia",
}
