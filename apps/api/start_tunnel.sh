#!/usr/bin/env bash
# Helper script to start ngrok tunnel for Archive Detective API
set -euo pipefail

PORT=${1:-8001}

echo "Starting ngrok tunnel on port $PORT..."
echo "API will be available at the ngrok URL shown below"
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "Error: ngrok is not installed"
    echo "Install from: https://ngrok.com/download"
    echo "Or use: brew install ngrok (macOS) / snap install ngrok (Linux)"
    exit 1
fi

# Start ngrok
ngrok http $PORT

