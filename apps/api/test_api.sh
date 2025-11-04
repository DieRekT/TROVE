#!/usr/bin/env bash
# Quick test script for Archive Detective API
set -euo pipefail

API_URL="${1:-http://127.0.0.1:8001}"

echo "Testing Archive Detective API at $API_URL"
echo ""

# Test ping
echo "1. Testing /api/ping..."
curl -s "$API_URL/api/ping" | jq '.' || echo "❌ Ping failed"
echo ""

# Test tunnel status
echo "2. Testing /api/tunnel/status..."
curl -s "$API_URL/api/tunnel/status" | jq '.' || echo "❌ Tunnel status failed"
echo ""

# Test QR code generation
echo "3. Testing /api/qrcode..."
curl -s "$API_URL/api/qrcode" -o /tmp/test_qr.png && echo "✅ QR code saved to /tmp/test_qr.png" || echo "❌ QR code generation failed"
echo ""

echo "✅ Basic API tests complete!"
echo ""
echo "To start the API: cd apps/api && ./run.sh"
echo "To start tunnel: cd apps/api && ./start_tunnel.sh"

