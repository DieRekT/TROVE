#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Trove app...${NC}"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run: bash setup.sh${NC}"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Kill any existing process on port 8000
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8000 is in use. Killing existing process...${NC}"
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Set environment variables
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

# Run with auto-reload and better error reporting
echo -e "${GREEN}✅ Starting uvicorn server on http://127.0.0.1:8000${NC}"
echo -e "${GREEN}📱 Auto-reload enabled - changes will refresh automatically${NC}"
echo ""

uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --log-level info \
  --access-log
