#!/usr/bin/env bash
# Simple script to start Expo with QR code

cd "$(dirname "$0")"

# Load nvm and use Node 18
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
nvm use 18 2>/dev/null || echo "⚠️  Using system Node (may have issues)"

# Set API base
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"

echo "🚀 Starting Expo..."
echo "📱 API Base: $EXPO_PUBLIC_API_BASE"
echo "🔗 QR Button: Tap the '🔗 QR' button in the app to configure API connection"
echo ""

npx expo start --tunnel

