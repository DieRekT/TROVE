#!/usr/bin/env bash
set -e

# Load nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Check if nvm loaded
if ! command -v nvm &> /dev/null; then
    echo "❌ nvm not found. Loading directly..."
    source "$NVM_DIR/nvm.sh"
fi

echo "✅ nvm version: $(nvm --version)"

# Install Node 18 if not installed
if ! nvm list 18 &>/dev/null | grep -q "v18"; then
    echo "📦 Installing Node 18..."
    nvm install 18 --latest-npm
fi

# Use Node 18
echo "🔄 Switching to Node 18..."
nvm use 18
echo "✅ Node version: $(node -v)"
echo "✅ npm version: $(npm -v)"

# Reinstall deps if needed
if [ ! -d "node_modules" ]; then
    echo "�� Installing dependencies..."
    npm install
fi

# Start Expo
echo "🚀 Starting Expo..."
export EXPO_PUBLIC_API_BASE="${EXPO_PUBLIC_API_BASE:-http://127.0.0.1:8001}"
npx expo start --tunnel --clear
