# Archive Detective - Running Status ✅

## ✅ What's Running

### Backend API
- **Status**: ✅ Running on http://127.0.0.1:8001
- **API Docs**: http://127.0.0.1:8001/docs (Swagger UI)
- **Demo Page**: file:///home/lucifer/Projects/trove/apps/api/demo.html

### Features Working
✅ Trove search - Returns newspaper articles from Australian archives
✅ API endpoints - All endpoints functional
✅ QR code generation - For tunnel/connection sharing
✅ Tunnel management - ngrok integration ready
✅ Sensitive Research Mode - Historical term expansion (opt-in)

## 🎯 Test Results

**Search "Australia"** - Found 5 results:
- Auburn News and Granville Electorate Gazetteer (1905-04-15)
- Daily Advertiser Wagga Wagga (1942-02-27)
- The Advertiser Adelaide (1896-03-11)
- The Propeller Hurstville (1932-12-02)
- The Daily News Perth (1902-11-12)

## 🌐 Browser Access

Two tabs should be open in Firefox:
1. **API Documentation** (Swagger): http://127.0.0.1:8001/docs
   - Interactive API testing
   - Try endpoints directly
   - See request/response schemas

2. **Demo Page**: file:///home/lucifer/Projects/trove/apps/api/demo.html
   - Live search interface
   - Pre-loaded with "Australia" search
   - Shows results with snippets
   - Toggle sensitive research mode

## 📱 Mobile App

The mobile app (Expo) needs Node 18 to run. To start:

```bash
cd ~/Projects/trove/apps/mobile
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 18
export EXPO_PUBLIC_API_BASE="http://127.0.0.1:8001"
npx expo start --tunnel
```

## 🚀 Quick Commands

**Start API**:
```bash
cd apps/api && ./run.sh
```

**Start Demo**:
```bash
cd apps/api && ./start_demo.sh
```

**Test Search**:
```bash
curl -X POST http://127.0.0.1:8001/api/trove/search \
  -H "Content-Type: application/json" \
  -d '{"q":"Sydney", "n":5}'
```

## 📊 API Endpoints

- `GET /api/ping` - Health check
- `POST /api/trove/search` - Search newspapers
- `GET /api/trove/article?id_or_url=...` - Get article text
- `POST /api/summarize` - AI summary (requires OPENAI_API_KEY)
- `POST /api/tunnel/start` - Start ngrok tunnel
- `GET /api/tunnel/status` - Get tunnel URL
- `GET /api/qrcode` - Generate QR code

## ✨ Capabilities Demonstrated

1. **Historical Newspaper Search** - Search millions of articles from Trove
2. **Full-Text Retrieval** - Get complete article text
3. **Sensitive Research Mode** - Expand queries with historical terms (opt-in)
4. **PDF Export** - Generate printable PDFs
5. **Tunnel Sharing** - QR codes for cross-network access
6. **AI Summaries** - Get concise summaries (if OpenAI key set)

Everything is working! 🎉


