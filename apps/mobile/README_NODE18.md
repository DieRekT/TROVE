# Running the Mobile App with Node 18

This app requires **Node 18** to work with Expo 52. Node 20 has TypeScript loader issues.

## Quick Start

### Option 1: Use the startup script (easiest)

```bash
cd apps/mobile
./start-expo.sh
```

This script automatically:
- Loads nvm
- Switches to Node 18 (from `.nvmrc`)
- Sets API base URL
- Starts Expo with tunnel

### Option 2: Manual setup

```bash
# Load nvm in your current shell
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# Switch to Node 18
cd apps/mobile
nvm use 18  # or: nvm use (auto-detects .nvmrc)

# Start Expo
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"
npx expo start --tunnel
```

### Option 3: Install nvm if missing

If nvm is not installed:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Then reload your shell or run:
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
nvm install 18
```

## Verify Setup

Run the check script:
```bash
cd apps/mobile
./check.sh
```

Should show:
- Node: v18.x.x
- Expo CLI version
- expo: ^52.0.0

## Troubleshooting

**"nvm: command not found"**
- Make sure nvm is installed and sourced in your shell
- Add to `~/.bashrc` or `~/.zshrc`:
  ```bash
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
  ```

**"Cannot find module"**
- Delete `node_modules` and reinstall:
  ```bash
  rm -rf node_modules package-lock.json
  nvm use 18
  npm install
  ```

**Expo still fails**
- Make sure you're using Node 18:
  ```bash
  node -v  # should show v18.x.x
  ```

