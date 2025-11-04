# Archive Detective - Quick Start Guide

## What Was Built

A complete mobile-first historical research app with:
- **FastAPI backend** (`apps/api/`) - Trove search, article fetching, PDF generation, AI summaries
- **Expo React Native app** (`apps/mobile/`) - iOS/Android mobile interface
- **Historical terms lexicon** (`packages/lexicon/`) - Opt-in sensitive research mode expansions

## First-Time Setup

### 1. Backend Setup (5 minutes)

```bash
cd apps/api

# Create virtual environment and install dependencies
./run.sh
```

**Before first run**, create `.env` file:
```bash
cp .env.example .env
# Edit .env and add your Trove API key
nano .env  # or use your preferred editor
```

Get Trove API key: https://trove.nla.gov.au/about/create-something/using-api/

The API will start on `http://127.0.0.1:8001`

### 2. Mobile App Setup (5 minutes)

```bash
cd apps/mobile

# Install dependencies
npm install

# Set API URL (adjust if needed)
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"

# Start development server
npx expo start --tunnel
```

**For physical devices:**
- Use your computer's local IP instead of `127.0.0.1`
- Example: `export EXPO_PUBLIC_API_BASE="http://192.168.1.100:8001"`

## Testing

1. **Backend**: Open `http://127.0.0.1:8001/api/ping` in browser - should return `{"ok": true}`
   - Or run: `cd apps/api && ./test_api.sh`
2. **Mobile**: Scan QR code with Expo Go app (Android/iOS)

## Using from Different Networks (Tunnel)

To access the API from a different network (e.g., your phone on mobile data):

### Option 1: Automatic (via API)

1. Start the API: `cd apps/api && ./run.sh`
2. In the mobile app, tap the **🔗 QR** button
3. The app will try to start a tunnel automatically
4. Scan the QR code to configure the API URL on another device

### Option 2: Manual (ngrok)

1. Start the API: `cd apps/api && ./run.sh`
2. In another terminal, start ngrok: `cd apps/api && ./start_tunnel.sh`
   - Or manually: `ngrok http 8001`
3. Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)
4. In the mobile app, tap **🔗 QR** button
5. The QR code will show the tunnel URL - scan it to configure

### Option 3: Using API Endpoints

The API provides endpoints for tunnel management:
- `POST /api/tunnel/start` - Start tunnel programmatically
- `GET /api/tunnel/status` - Get current tunnel URL
- `GET /api/qrcode?url=...` - Generate QR code for any URL

## Building for Production

### Android APK
```bash
cd apps/mobile
npm install -g eas-cli
eas login
npm run build:android
```

### iOS (requires Apple Developer account)
```bash
cd apps/mobile
npm run build:ios
```

## Project Structure

```
archive-detective/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py         # API endpoints
│   │   │   ├── trove.py        # Trove API client
│   │   │   ├── text_clean.py   # HTML to text conversion
│   │   │   └── models.py       # Pydantic models
│   │   ├── requirements.txt
│   │   ├── run.sh              # Startup script
│   │   └── .env.example
│   └── mobile/                 # Expo React Native app
│       ├── App.tsx             # Main app component
│       ├── src/
│       │   ├── api.ts          # API client
│       │   ├── screens/
│       │   │   ├── SearchScreen.tsx
│       │   │   └── ArticleScreen.tsx
│       │   └── components/
│       │       ├── TermModeBanner.tsx
│       │       └── ResultItem.tsx
│       ├── package.json
│       ├── app.config.ts
│       └── eas.json            # EAS build config
└── packages/
    └── lexicon/
        └── historical_terms.json  # Sensitive mode expansions
```

## Key Features

✅ **Trove Search** - Search Australian newspaper archives
✅ **Sensitive Research Mode** - Opt-in historical term expansion (with guardrails)
✅ **Full-Text Articles** - Fetch and read complete articles
✅ **PDF Export** - One-tap print to PDF
✅ **Text-to-Speech** - On-device reading aloud
✅ **AI Summaries** - Get concise summaries (requires OpenAI API key)

## Troubleshooting

**API 500 errors:**
- Check `TROVE_API_KEY` in `apps/api/.env`
- Verify key works: https://trove.nla.gov.au/api/v3/result?key=YOUR_KEY&category=newspaper&q=test

**Mobile can't reach API:**
- Confirm `EXPO_PUBLIC_API_BASE` matches your API server
- For physical devices, use local IP not `127.0.0.1`
- Ensure both devices are on same network

**Summaries not working:**
- Add `OPENAI_API_KEY` to `apps/api/.env` (optional feature)

## Next Steps

See `ARCHIVE_DETECTIVE_README.md` for full documentation and future enhancements.

