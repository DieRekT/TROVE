#!/usr/bin/env bash
set -euo pipefail

# Load nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Use Node 18 from .nvmrc
cd "$(dirname "$0")"
[ -f .nvmrc ] && nvm use

# Set API base
export EXPO_PUBLIC_API_BASE="${EXPO_PUBLIC_API_BASE:-http://127.0.0.1:8001}"

# Start Expo
echo "Starting Expo with Node $(node -v)..."
npx expo start --tunnel --clear

