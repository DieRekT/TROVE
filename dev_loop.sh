#!/bin/bash
# Daily dev loop - run quality checks and start server
# Usage: bash dev_loop.sh

set -e

cd "$(dirname "$0")"

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️  .venv not found. Creating..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install -U ruff black mypy pytest pytest-asyncio anyio
fi

echo "🔍 Running quality checks..."
ruff check --fix .
black .
echo "✅ Code formatted"

echo "🧪 Running tests..."
pytest -q || echo "⚠️  Some tests failed, but continuing..."

echo "🚀 Starting server..."
echo "Open http://127.0.0.1:8000 in your browser"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

