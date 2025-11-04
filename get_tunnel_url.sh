#!/bin/bash
# Get public tunnel URL without needing localhost access

echo "🔍 Finding active ngrok tunnel URLs..."
echo ""

# Method 1: Check ngrok API
if curl -s http://127.0.0.1:4040/api/tunnels > /dev/null 2>&1; then
    echo "✅ Found tunnel via ngrok API:"
    curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = [t for t in data.get('tunnels', []) if t.get('proto') == 'http']
    if tunnels:
        for t in tunnels:
            print(f\"  🌐 Public URL: {t['public_url']}\")
            print(f\"     → Points to: {t.get('config', {}).get('addr', 'unknown')}\")
    else:
        print('  No HTTP tunnels found')
except Exception as e:
    print(f'  Error: {e}')
" 2>/dev/null
    echo ""
fi

# Method 2: Check via web app API
echo "📡 Checking via web app API:"
WEB_URL=$(curl -s http://127.0.0.1:8000/api/tunnel/public-url 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('url', 'N/A'))" 2>/dev/null)
if [ "$WEB_URL" != "N/A" ] && [ "$WEB_URL" != "null" ]; then
    echo "  ✅ Public URL: $WEB_URL"
    echo ""
    echo "📋 You can access this URL directly:"
    echo "   $WEB_URL"
    echo ""
    echo "📱 Or use the web app QR modal:"
    echo "   http://127.0.0.1:8000 (click '📱 Connect' button)"
else
    echo "  ❌ No tunnel found via API"
    echo ""
    echo "💡 To start a tunnel:"
    echo "   1. Visit http://127.0.0.1:8000"
    echo "   2. Click '📱 Connect' button"
    echo "   3. Click '🌐 Start Public Tunnel'"
    echo ""
    echo "   Or run manually: ngrok http 8000"
fi

