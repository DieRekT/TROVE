#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env || true
echo "Fill TROVE_API_KEY in apps/api/.env"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

