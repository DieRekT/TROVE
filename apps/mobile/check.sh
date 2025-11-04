#!/usr/bin/env bash
set -euo pipefail
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
cd "$(dirname "$0")"
[ -f .nvmrc ] && nvm use
echo "Node:" $(node -v)
echo "npm :" $(npm -v)
echo "Expo CLI:" $(npx expo --version || true)
node -e "try{const p=require('./package.json');console.log('expo:',p.dependencies.expo)}catch(e){console.error(e)}"

