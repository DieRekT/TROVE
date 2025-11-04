#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Done. Now: cp .env.example .env && edit your TROVE_API_KEY, then: bash run.sh"

