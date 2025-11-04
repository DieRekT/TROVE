#!/bin/bash
# One-shot workflow script for daily dev loop
# Run: bash tools/audit_fix.sh

set -e

cd "$(dirname "$0")/.."

echo "🔍 Running code quality checks..."

# Activate venv if available
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run ruff
echo "📋 Running ruff..."
ruff check --fix .

# Run black
echo "🎨 Running black..."
black .

# Run mypy (non-blocking)
echo "🔬 Running mypy..."
mypy app || true

# Run tests
echo "🧪 Running tests..."
pytest -q

echo "✅ All checks passed!"

