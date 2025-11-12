#!/bin/bash
# Run script for Archive Detective backend
set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load .env if it exists
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for TROVE_API_KEY
if [ -z "$TROVE_API_KEY" ] || [ "$TROVE_API_KEY" = "your_trove_api_key_here" ]; then
    echo "⚠️  WARNING: TROVE_API_KEY not set in .env"
    echo "   Please edit .env and set your TROVE_API_KEY"
    echo "   Continuing anyway (will fail on API calls)..."
fi

# Run the server
echo "🚀 Starting Archive Detective API on http://127.0.0.1:8000"
echo "   Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

