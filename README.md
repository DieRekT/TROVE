# Trove - AI-Powered Historical Research Platform

A comprehensive, multi-component research platform for exploring Australian newspaper archives (Trove) with AI assistance. Built with FastAPI, featuring advanced search, context-aware AI chat, article tracking, and report generation.

## 🚀 Quick Start

```bash
# Setup and install dependencies
bash setup.sh

# Configure API keys
cp .env.example .env
# Edit .env and add your TROVE_API_KEY (and optionally OPENAI_API_KEY)

# Start the application
bash run.sh

# Open in browser
open http://127.0.0.1:8000/dashboard
```

## 🎯 What's Included

### Main Web Application (Port 8000)
- **Dashboard** - Overview and quick actions
- **Advanced Search** - Multi-category search with filters, facets, and natural language
- **Article Reader** - Full-text reading with text-to-speech (TTS)
- **Archive Detective Chat** - AI-powered research assistant with context awareness
- **Research Desk** - Alternative AI conversation interface
- **Collections** - Article organization and management
- **Report Studio** - PDF report generation
- **Timeline View** - Chronological event visualization
- **Context Tracking** - Automatic article tracking with SQLite persistence

### Archive Detective API (Port 8001)
- Mobile/automation backend
- Trove search, article fetching, PDF generation
- Tunnel management and QR code generation

### Mobile Application (Expo React Native)
- iOS/Android support
- Search, article viewing, TTS, PDF export
- QR code connection

## 📍 Key URLs

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/dashboard` | Home dashboard |
| `http://127.0.0.1:8000/search` | Advanced search interface |
| `http://127.0.0.1:8000/reader?id=...` | Article reader with TTS |
| `http://127.0.0.1:8000/chat` | Archive Detective AI chat |
| `http://127.0.0.1:8000/desk` | Research desk |
| `http://127.0.0.1:8000/studio` | Report studio |
| `http://127.0.0.1:8000/status` | System status |
| `http://127.0.0.1:8001/docs` | Archive Detective API docs |

## 🧪 Sample Data & Smoke Tests

- `scripts/seed_sample_research.py` seeds three thematic research topics, pins example articles, and exercises the pin, card, summary, and brief endpoints via FastAPI's TestClient.
- Run it anytime you need a fresh set of demo data:

```bash
python scripts/seed_sample_research.py
```

- The script writes `app/data/sample_briefs.json` with captured responses so brief/card features always have something to validate.

## 🔑 Environment Variables

Required:
- `TROVE_API_KEY` - Your Trove API key (get one at https://trove.nla.gov.au/about/create-something/using-api/)

Optional:
- `OPENAI_API_KEY` - For AI summaries and chat (enables advanced features)
- `ARCHIVE_DETECTIVE_ENABLED` - Enable Archive Detective features
- `CONTEXT_DB` - Path to context database (default: `app/data/context.db`)
- `CONTEXT_MAX_PER_SESSION` - Max articles per session (default: 50)

## ✨ Key Features

- **Advanced Search** - Multi-category search with filters (year, place, format, sort)
- **Quick Filters** - One-click chips for popular publications, places, formats, and date ranges
- **Context-Aware AI** - Chat assistant remembers all articles you've read
- **Text-to-Speech** - Read articles aloud with adjustable speed
- **Article Tracking** - Automatic tracking with pin/unpin functionality
- **Report Generation** - Create PDF reports with article summaries
- **Image Management** - Download and save images from State Library NSW
- **Mobile Support** - QR code connection, responsive design
- **SQLite Persistence** - Context tracking survives restarts

## 📚 Documentation

- `VISION_SNAPSHOT.md` - **Single-page vision snapshot** (current state, roadmap, next tasks)
- `VISION.md` - Complete project vision and workflows
- `FEATURES.md` - Detailed features list
- `STATUS.md` - System status and health
- `COMPREHENSIVE_BUILD_REPORT.md` - Complete build inventory
- `QUICK_START_GUIDE.md` - Quick start steps

## 🏗️ Architecture

- **Backend**: FastAPI 0.115+ with Pydantic v2, SQLite
- **Frontend**: Jinja2 templates, vanilla JavaScript, modern CSS
- **AI**: OpenAI GPT integration with fallback systems
- **Mobile**: Expo React Native (iOS/Android)
- **Type Safety**: Full type hints, Pydantic models

## 📊 Statistics

- **58+ API endpoints** across multiple applications
- **12 web pages** with modern UI/UX
- **50+ documented features**
- **10,000+ lines of code** with type safety

## 🔗 Related Projects

- Archive Detective API: `apps/api/` (Port 8001)
- Mobile App: `apps/mobile/` (Expo)
- Backend Services: `backend/` (Additional services)

## 📝 Notes

- Uses Trove API v3 (`/v3/result` endpoint)
- Respect Trove terms of use for metadata and digitised content
- Context tracking uses SQLite (WAL mode) for performance
- All features work without OpenAI, but AI features require `OPENAI_API_KEY`

For detailed information, see `COMPREHENSIVE_BUILD_REPORT.md`.
