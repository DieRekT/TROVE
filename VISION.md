# 🎯 Trove Project - Full Vision & Workflow Guide

**Last Updated:** $(date)

## 🗺️ Project Architecture Overview

This is a **multi-component research platform** for exploring Trove (Australian newspaper archives) with AI assistance. Here's the complete picture:

```
┌─────────────────────────────────────────────────────────────┐
│                    TROVE RESEARCH PLATFORM                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  MAIN WEB APP    │      │  ARCHIVE DETECTIVE│            │
│  │  Port 8000       │      │  API Port 8001    │            │
│  │                  │      │                   │            │
│  │  • Dashboard     │      │  • Search API     │            │
│  │  • Search        │      │  • Article fetch  │            │
│  │  • Reader        │      │  • AI Summaries   │            │
│  │  • Chat/Desk     │      │  • PDF Export     │            │
│  │  • Collections   │      │  • Tunnel/QR      │            │
│  │  • Studio        │      │                   │            │
│  │  • Timeline      │      │                   │            │
│  └──────────────────┘      └──────────────────┘            │
│           │                           │                     │
│           └───────────┬───────────────┘                     │
│                       │                                     │
│              ┌────────▼────────┐                           │
│              │  CONTEXT STORE  │                           │
│              │  SQLite DB      │                           │
│              │  (app/data/)     │                           │
│              └─────────────────┘                           │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  MOBILE APP      │      │  DATA OUTPUTS    │            │
│  │  (Expo/React)    │      │                  │            │
│  │                  │      │  • CSV reports   │            │
│  │  • Search        │      │  • PDF reports   │            │
│  │  • Article view  │      │  • Timeline data │            │
│  │  • QR connect    │      │  • Queries       │            │
│  └──────────────────┘      └──────────────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start - Single Command

```bash
# Start main app (everything)
cd /home/lucifer/Projects/trove
bash run.sh
```

Then open: **http://127.0.0.1:8000/dashboard**

---

## 📍 All Entry Points & URLs

### Main Web Application (Port 8000)

| URL | Purpose | What You'll See |
|-----|---------|-----------------|
| `/` or `/dashboard` | **Home Dashboard** | Overview, stats, quick links |
| `/search` | **Search Interface** | Search Trove, filter results, pin articles |
| `/reader?id=...` | **Article Reader** | Full article text, TTS, citations |
| `/chat` | **Archive Detective** | AI chat with context-aware research assistant |
| `/desk` | **Research Desk** | Alternative AI conversation interface |
| `/collections` | **Collections Board** | Saved articles, boards, pins |
| `/studio` | **Report Studio** | Drafting interface for reports |
| `/timeline` | **Timeline View** | Event ribbon, chronological view |
| `/status` | **System Status** | Health, tunnel status, metrics |

### Archive Detective API (Port 8001)

| URL | Purpose | What You'll See |
|-----|---------|-----------------|
| `http://127.0.0.1:8001/docs` | **API Docs** | Swagger UI, interactive testing |
| `http://127.0.0.1:8001/api/trove/search` | **Search Endpoint** | JSON API for searches |
| `file:///.../apps/api/demo.html` | **Demo Page** | Live search interface |

### API Endpoints (Main App)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/context` | GET | Get tracked articles |
| `/api/context/track` | POST | Track an article |
| `/api/context/pin/{id}` | POST | Pin article |
| `/api/context/unpin/{id}` | POST | Unpin article |
| `/api/context/pack` | GET | Get formatted context for AI |
| `/api/item/{id}` | GET | Get article details |
| `/api/explain` | POST | Explain selected text |
| `/api/define` | POST | Define selected term |
| `/api/translate` | POST | Translate text |
| `/api/tunnel/status` | GET | Check ngrok tunnel |
| `/api/qrcode` | GET | Generate QR code for mobile |

---

## 🔄 Recommended Workflows

### Workflow 1: Research Session (Standard)

```
1. Start: http://127.0.0.1:8000/dashboard
   ↓
2. Search: Click "Search" → Enter query → Browse results
   ↓
3. Explore: Click article → Preview drawer → Click "📖 Open Reader"
   ↓
4. Pin Important: Click "📌 Pin" on articles you want to cite
   ↓
5. Chat: Go to /chat → Ask questions about your research
   ↓
6. Export: Use /studio to draft reports, or check /outputs for CSVs
```

### Workflow 2: AI-Assisted Research

```
1. Start: http://127.0.0.1:8000/desk
   ↓
2. Chat: Ask AI to help find articles
   ↓
3. AI Searches: Uses /search internally
   ↓
4. Review: Click through to articles, pin what's useful
   ↓
5. Follow-up: Ask AI to summarize, compare, or explain
   ↓
6. Build: Use /studio to create reports from pinned articles
```

### Workflow 3: Mobile Research

```
1. Start API: cd apps/api && ./run.sh  (port 8001)
   ↓
2. Get QR: Visit http://127.0.0.1:8000/status → Check tunnel
   ↓
3. Scan QR: Use mobile app to connect
   ↓
4. Search: Use mobile interface
   ↓
5. Sync: Data syncs back to main app
```

### Workflow 4: Batch Query Processing

```
1. Prepare: Edit queries/trove_queries.csv
   ↓
2. Run: Use Archive Detective batch processing
   ↓
3. Review: Check outputs/ folder for reports
   ↓
4. Analyze: Import CSV into timeline view
```

---

## 🎯 Key Features by Component

### Main Web App (Port 8000)

**✅ Search System**
- Multi-category search (newspaper, magazine, book, image, etc.)
- Advanced filters (year range, place, format, sort)
- Result previews with full metadata
- Pin buttons on every result
- Auto-tracking to context store

**✅ Reader System**
- Full article text display
- Text-to-speech (TTS) with speed control
- Citation generation
- Explain/Define/Translate on text selection
- Scan viewer when available

**✅ Context System**
- Automatic article tracking
- Pin/unpin functionality
- SQLite persistence (survives restarts)
- Session management
- Context packing for AI (≤3500 chars)

**✅ Chat/AI System**
- Context-aware responses
- Uses tracked articles as context
- Commands: `/cite`, `/read`, `/search`, `/help`
- Integrated with Archive Detective

**✅ Collections & Timeline**
- Collections board view
- Timeline visualization
- Report studio for drafting

### Archive Detective API (Port 8001)

**✅ Core API**
- Trove search endpoint
- Article text fetching
- PDF generation
- AI summarization
- Tunnel management

**✅ Mobile Support**
- QR code generation
- ngrok tunnel integration
- RESTful API design

### Mobile App (Expo)

**✅ Mobile Interface**
- Search interface
- Article viewing
- QR code connection
- Offline support (planned)

---

## 📊 Data Flow

```
User Action → Frontend → API Endpoint → Context Store → Database
                                    ↓
                              Archive Detective
                                    ↓
                              Trove API (external)
```

**Example:**
1. User clicks article in search → `/api/item/{id}` called
2. Article fetched → `add_article_to_context()` called
3. Saved to SQLite → `app/data/context.db`
4. Available in chat → `pack_for_prompt()` formats it
5. AI uses it in responses

---

## 🔧 Component Status

### ✅ Fully Operational

- [x] Main web app (port 8000)
- [x] Search interface
- [x] Reader with TTS
- [x] Context tracking (SQLite)
- [x] Pin/unpin functionality
- [x] Chat integration
- [x] Archive Detective API (port 8001)
- [x] QR code generation
- [x] PDF export
- [x] Timeline view
- [x] Collections board

### 🚧 In Progress / Partial

- [ ] Mobile app (needs Node 18 setup)
- [ ] Advanced report generation
- [ ] Batch query processing automation
- [ ] Collection sharing

---

## 📁 Key Directories

```
/home/lucifer/Projects/trove/
├── app/                    # Main FastAPI application
│   ├── archive_detective/  # Archive Detective agent
│   ├── data/               # SQLite database (context.db)
│   └── main.py            # Main routes & endpoints
├── templates/             # HTML templates
├── static/                # CSS, JS assets
├── outputs/               # Generated reports, CSVs, PDFs
├── queries/               # Query CSV files
├── apps/
│   ├── api/               # Archive Detective API (port 8001)
│   └── mobile/            # Expo mobile app
└── packages/
    └── lexicon/           # Historical terms for search expansion
```

---

## 🎓 Understanding the Context System

The context system is **automatic** - you don't need to manually manage it:

1. **Auto-tracking**: When you click an article, it's automatically saved
2. **Pin for importance**: Click 📌 to mark articles for AI citation
3. **Chat uses context**: AI automatically knows what you've read
4. **Persistence**: Everything saved to SQLite, survives restarts

**Check your context:**
- Visit `/chat` → Click "📚 Research (X)" button
- Or call `/api/context` directly

---

## 🚨 Common Issues & Solutions

### "I can't see my articles"
- Check: `app/data/context.db` exists
- Visit: `/status` to check system health
- Try: `/api/context` to see raw data

### "Chat doesn't know what I read"
- Check: Articles are being tracked (click them first)
- Check: Context store is initialized (see logs)
- Try: Pin articles explicitly (📌 button)

### "Search returns nothing"
- Check: API key in `.env` file
- Check: Network connection
- Check: Query isn't too restrictive

### "Mobile app won't connect"
- Start API: `cd apps/api && ./run.sh`
- Check tunnel: Visit `/status` or `/api/tunnel/status`
- Get QR: `/api/qrcode` endpoint

---

## 🎯 Quick Navigation Cheat Sheet

```
Dashboard    →  /dashboard    (Overview, entry point)
Search       →  /search       (Find articles)
Reader       →  /reader?id=... (Read articles)
Chat         →  /chat         (AI assistant)
Desk         →  /desk         (Research desk)
Collections  →  /collections   (Saved articles)
Studio       →  /studio       (Report drafting)
Timeline     →  /timeline     (Chronological view)
Status       →  /status       (System health)
```

---

## 💡 Pro Tips

1. **Start at Dashboard**: It's your command center
2. **Pin Early**: Pin articles as you discover them
3. **Use Chat**: Ask "What articles have I read?" to see context
4. **Batch Queries**: Use `queries/trove_queries.csv` for research
5. **Check Outputs**: Your reports are in `outputs/` folder
6. **Mobile Access**: Use QR code from `/status` page

---

## 🔗 Related Documentation

- `README.md` - Basic setup
- `RESEARCH_DEMO.md` - Feature walkthrough
- `STATUS.md` - System status details
- `APP_STATUS.md` - Archive Detective status
- `QUICK_START_GUIDE.md` - Quick start steps

---

## 🎉 You Have Full Vision!

Everything is connected:
- **Web app** for desktop research
- **API** for mobile/automation
- **Context store** tracks everything
- **AI** uses your research as context
- **Outputs** generate reports

**Start here:** http://127.0.0.1:8000/dashboard

