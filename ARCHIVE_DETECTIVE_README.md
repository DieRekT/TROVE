# Archive Detective

**Mobile-first historical research app** for finding and reading primary sources from Trove (and eventually other archives). Built for household researchers, family historians, teachers, and real-life detectives.

## Features

- 🔍 **Trove search** with full-text article retrieval
- ⚠️ **Sensitive Research Mode** (opt-in): expands queries with historical/offensive terms for better archival recall
- 📝 **On-device TTS**: read articles aloud
- 📄 **One-tap PDF export**: print or share articles
- 🤖 **AI summaries**: get concise summaries with citations (requires OpenAI API key)

## Architecture

Monorepo structure:
- `apps/api/` - FastAPI backend (Trove proxy, text cleaning, summaries)
- `apps/mobile/` - Expo React Native app (iOS + Android)
- `packages/lexicon/` - Historical term expansions (opt-in sensitive mode)

## Quick Start

### Backend (API)

```bash
cd apps/api
./run.sh
```

**Before running**, edit `apps/api/.env` and add your Trove API key:
```
TROVE_API_KEY=your-key-here
OPENAI_API_KEY=optional-for-summaries
```

Get a Trove API key at: https://trove.nla.gov.au/about/create-something/using-api/

The API will run on `http://127.0.0.1:8001`

### Mobile App

```bash
cd apps/mobile

# Install dependencies
npm install

# Set API base URL (adjust if API is on a different host)
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"

# Start Expo development server
npx expo start --tunnel
```

**Testing on device:**
- **Android**: Install Expo Go app, scan QR code
- **iOS**: Install Expo Go app, scan QR code (requires Expo account)

**Building for production:**

```bash
# Install EAS CLI
npm install -g eas-cli
eas login

# Build Android APK
npm run build:android

# Build iOS (requires Apple Developer account)
npm run build:ios
```

## Sensitive Research Mode

By default, **Sensitive Research Mode is OFF**. When enabled:

1. The app shows a clear banner explaining that historically offensive terms may be included
2. The API expands queries with historical/offensive terms from `packages/lexicon/historical_terms.json`
3. Terms are labeled as *historical/offensive* for context
4. Usage is logged locally (private, on-device)

**Why this exists:** Historical newspapers used offensive language. To find primary sources, we sometimes need to search with the terms that were used at the time. This is **research-only** functionality with clear guardrails.

## API Endpoints

- `GET /api/ping` - Health check
- `POST /api/trove/search` - Search Trove newspapers
  ```json
  {
    "q": "search query",
    "n": 20,
    "sensitive_mode": false
  }
  ```
- `GET /api/trove/article?id_or_url=...&pdf=false` - Fetch article text (or PDF if `pdf=true`)
- `POST /api/summarize` - Get AI summary (requires `OPENAI_API_KEY`)

## Troubleshooting

**API returns 500 errors:**
- Check that `TROVE_API_KEY` is set in `apps/api/.env`
- Verify Trove API key is valid at https://trove.nla.gov.au/api/v3/result?key=YOUR_KEY&category=newspaper&q=test

**Mobile app can't reach API:**
- Confirm `EXPO_PUBLIC_API_BASE` matches your API server URL
- If using Expo Go with tunnel, ensure tunnel is active
- For physical devices, use your computer's local IP (e.g., `http://192.168.1.100:8001`) instead of `127.0.0.1`

**Trove returns items but no article text:**
- Some articles lack OCR text; the record exists but text extraction may fail
- Check the article ID and try accessing it directly on Trove website

**Summaries not working:**
- Summaries require `OPENAI_API_KEY` in `apps/api/.env`
- If missing, the app will show "(Summaries disabled)" message

## Next Steps

Once MVP is solid, consider:

1. **Research Notebook**: Save clips, highlights, citations (CSL-JSON/BibTeX export)
2. **Watchlists**: Saved queries that refresh weekly; "new since last visit"
3. **Multi-source**: Add NAA, State Library catalogues, Papers Past (NZ), IIIF ingest
4. **De-bias helpers**: Show side-by-side "historical label → modern terminology" in summaries
5. **Kid-safe profile**: Disables sensitive mode entirely, hides slur matches

## License

MIT (or your preferred license)

## Contributing

This is a research tool for historical investigation. Please use responsibly and respect the sensitive nature of historical materials.

