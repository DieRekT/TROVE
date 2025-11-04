#!/usr/bin/env bash
# Start API and open demo in browser
set -e

cd "$(dirname "$0")"

# Check if API is running
if ! curl -s http://127.0.0.1:8001/api/ping > /dev/null 2>&1; then
    echo "Starting API server..."
    ./run.sh &
    sleep 3
fi

# Wait for API to be ready
for i in {1..10}; do
    if curl -s http://127.0.0.1:8001/api/ping > /dev/null 2>&1; then
        echo "✅ API is running"
        break
    fi
    sleep 1
done

# Open browser
echo "Opening demo page..."
if command -v firefox &> /dev/null; then
    firefox "http://127.0.0.1:8001/docs" "file://$(pwd)/demo.html" &
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:8001/docs" &
    xdg-open "file://$(pwd)/demo.html" &
else
    echo "Open these URLs in your browser:"
    echo "  API Docs: http://127.0.0.1:8001/docs"
    echo "  Demo: file://$(pwd)/demo.html"
fi

echo ""
echo "✅ Demo ready!"
echo "   API: http://127.0.0.1:8001/docs"
echo "   Demo: file://$(pwd)/demo.html"


