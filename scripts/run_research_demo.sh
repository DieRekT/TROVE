#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs) || true
fi

# Create outputs directory
mkdir -p outputs/research

# Run the server
echo "Starting Trove Deep Research server..."
echo "Access the research interface at: http://localhost:8000/research"
echo ""
echo "Example research questions:"
echo "  - History of phosphate mining approvals in NSW's North Coast (1970–1995)"
echo "  - Origins and community response to the term 'blacks' in 1972 Australian press discourse"
echo "  - Impacts of Cyclone Zoe analogs on Clarence River flooding patterns (1940–1975)"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

