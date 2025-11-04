#!/usr/bin/env bash
# appfresh - Run app and open in Firefox

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔥 Starting app and opening in Firefox...${NC}"

# Start the app in background
bash run.sh &
APP_PID=$!

# Wait for server to be ready
echo -e "${YELLOW}⏳ Waiting for server to start...${NC}"
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Server is ready!${NC}"
        break
    fi
    sleep 1
done

# Open in Firefox
echo -e "${GREEN}🌐 Opening http://127.0.0.1:8000 in Firefox...${NC}"
firefox http://127.0.0.1:8000 2>/dev/null &

echo -e "${GREEN}✅ Done! Server running in background (PID: $APP_PID)${NC}"
echo -e "${YELLOW}💡 To stop: kill $APP_PID or pkill -f uvicorn${NC}"

# Wait for the background process
wait $APP_PID

