#!/bin/bash
# Quick tunnel status checker

echo "🔍 Checking ngrok tunnel status..."
echo ""

# Check if ngrok web interface is running
if curl -s http://127.0.0.1:4040/api/tunnels > /dev/null 2>&1; then
    echo "✅ ngrok web interface is running on http://127.0.0.1:4040"
    echo ""
    echo "Active tunnels:"
    curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool 2>/dev/null | grep -A 5 '"public_url"' || echo "  (Cannot parse tunnel data)"
    echo ""
    echo "📱 Open http://127.0.0.1:4040 in your browser to see all tunnels"
else
    echo "❌ ngrok web interface not accessible (port 4040)"
    echo ""
    echo "Checking for ngrok processes:"
    ps aux | grep -i ngrok | grep -v grep || echo "  No ngrok processes found"
fi

echo ""
echo "💡 Options:"
echo "  1. Visit http://127.0.0.1:8000 and click '📱 Connect' button"
echo "  2. Use local network IP (same WiFi): http://127.0.0.1:8000/api/local-ip"
echo "  3. Kill existing tunnels: pkill ngrok"
echo "  4. Start fresh: ngrok http 8000"

