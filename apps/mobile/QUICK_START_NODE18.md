# Quick Start - Run This Now

## Step 1: Open a NEW terminal window

The nvm commands need to run in a fresh shell that loads `.bashrc`.

## Step 2: Run these commands

```bash
cd ~/Projects/trove/apps/mobile

# Load nvm (copy-paste this exactly)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Verify nvm works
nvm --version

# Install Node 18 (if not already installed)
nvm install 18

# Switch to Node 18
nvm use 18

# Verify Node version (should show v18.x.x)
node -v

# Start Expo
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"
npx expo start --tunnel
```

## Alternative: Use the script

If the above doesn't work, run:

```bash
cd ~/Projects/trove/apps/mobile
bash install-node18-and-start.sh
```

## If nvm still doesn't work

You may need to restart your terminal or run:

```bash
source ~/.bashrc
```

Then try the commands above again.

## What to expect

- Node version should show **v18.x.x** (not v20)
- Expo should start without the TypeScript error
- QR code will appear for scanning

