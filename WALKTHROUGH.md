# 🎯 Troveing App - Complete Walkthrough

## 📚 Overview

**Troveing** is a research assistant for Trove archives that combines:
- **Search** - Browse millions of articles from Trove
- **AI Context Store** - Persistent SQLite-based research memory
- **Archive Detective Chat** - AI assistant that cites your research
- **Reader** - Full-text reading with TTS
- **Report Studio** - Build PDF reports from your research

---

## 🏗️ Architecture

### **Backend (FastAPI)**
- **`app/main.py`** - Main FastAPI app with routes
- **`app/context_store.py`** - SQLite persistence layer
- **`app/context_api.py`** - REST API for context management
- **`app/archive_detective/router.py`** - Chat & AI features
- **`app/services.py`** - Trove API integration

### **Frontend (Templates)**
- **`templates/search.html`** - Search interface with pin buttons
- **`templates/chat.html`** - Archive Detective chat
- **`templates/reader.html`** - Article reader with TTS

### **Database**
- **`app/data/context.db`** - SQLite database (auto-created)
  - `sessions` table - Session tracking
  - `articles` table - Research context (pinned, views, timestamps)

---

## 🔄 How It All Works Together

### **1. Search → Auto-Tracking Flow**

```
User searches → Results appear → User clicks article
    ↓
Article automatically tracked via `/api/context/track`
    ↓
Saved to SQLite (app/data/context.db)
    ↓
Available for AI chat context
```

**What happens:**
- When you click an article in search results, it's automatically sent to `/api/context/track`
- The article is stored in SQLite with: `trove_id`, `title`, `date`, `source`, `url`, `snippet`
- This happens silently in the background - no popup needed

### **2. Pin/Unpin System**

**Pin Button (📌)** on each search result:
- Click → Article pinned in SQLite (`pinned=1`)
- Pinned articles appear **first** in AI context
- Visual feedback: 📌 → 📌✅ when pinned

**Why pin?**
- Pinned articles are prioritized in AI chat prompts
- They're included even when context is full (max 50 articles)
- Perfect for key sources you want the AI to always cite

### **3. AI Chat with Context**

**Archive Detective Chat** (`/chat`):
- Uses `pack_for_prompt()` from SQLite
- Builds compact bibliography (≤3500 chars)
- **Pinned articles first**, then most recent
- AI receives context automatically with every message

**Example flow:**
```
User: "What did the gold articles say?"
    ↓
Chat handler calls pack_for_prompt(session_id, max_chars=3500)
    ↓
Returns: "Research Context:\n- Article 1 (pinned)\n- Article 2..."
    ↓
AI receives this context + user message
    ↓
AI responds citing specific articles by title/date/source
```

### **4. Commands Available**

**`/cite <article_id>`** - Pin and cite an article
- Fetches article
- Adds to context
- Pins it automatically
- Shows confirmation

**`/read <article_id>`** - Read article (adds to context)
**`/search <query>`** - Search Trove
**`/help`** - Show all commands

---

## 📊 Context Store API

### **Endpoints**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/context` | GET | List all articles for session |
| `/api/context/track` | POST | Track an article |
| `/api/context/pin/{trove_id}` | POST | Pin an article |
| `/api/context/unpin/{trove_id}` | POST | Unpin an article |
| `/api/context/pack` | GET | Get packed context for prompts |
| `/api/context` | DELETE | Clear session |

### **Session Management**

**How sessions work:**
1. Default: Uses `IP + User-Agent` hash (32 chars)
2. Optional: Pass `X-Session-Id` header for stable sessions
3. Sessions persist across restarts (SQLite)

---

## 🔍 Key Features

### **1. Automatic Tracking**
- Articles tracked when:
  - Clicked in search results
  - Opened in preview drawer
  - Opened in reader
  - Used with `/read` or `/cite` commands

### **2. Persistent Memory**
- SQLite database survives server restarts
- Max 50 articles per session (auto-pruned)
- Oldest unpinned articles removed first

### **3. Smart Prompt Packing**
- Compact bibliography format
- Character limit: 3500 chars (configurable)
- Format: `- Title (Date, Source). Snippet: ... URL: ...`
- Pinned articles prioritized

### **4. Write-Through Pattern**
- In-memory `research_context.py` still works
- Automatically writes through to SQLite
- Best of both: fast in-memory + persistent storage

---

## 🎮 User Workflows

### **Workflow 1: Research Session**

```
1. Search for articles
2. Click articles to read (auto-tracked)
3. Pin important ones (📌 button)
4. Go to Archive Detective chat
5. Ask: "Summarize the gold discoveries I found"
6. AI cites your pinned/recent articles
```

### **Workflow 2: Quick Citation**

```
1. Find article in search
2. Click 📌 to pin
3. Or use: /cite <article_id> in chat
4. Article now prioritized for AI
```

### **Workflow 3: Deep Research**

```
1. Search multiple topics
2. Read 10-20 articles
3. Pin 3-5 key sources
4. Chat with AI about patterns/themes
5. AI synthesizes across all your research
```

---

## 🛠️ Technical Details

### **Database Schema**

```sql
sessions (
  sid TEXT PRIMARY KEY,
  created_at REAL,
  last_seen REAL
)

articles (
  sid TEXT,
  trove_id TEXT,
  title TEXT,
  date TEXT,
  source TEXT,
  url TEXT,
  snippet TEXT,
  pinned INTEGER DEFAULT 0,
  views INTEGER DEFAULT 0,
  first_seen REAL,
  last_seen REAL,
  PRIMARY KEY (sid, trove_id)
)
```

### **Context Packing Algorithm**

1. Query articles: `ORDER BY pinned DESC, last_seen DESC`
2. Build compact lines: `- Title (Date, Source). Snippet...`
3. Stop when total chars > max_chars (3500)
4. Return formatted text + count

### **Session ID Generation**

```python
# Default (IP + UA hash)
sid = sha256(f"{ip}|{ua}")[:32]

# Or use header
sid = request.headers.get("X-Session-Id")
```

---

## 🚀 Usage Examples

### **Track an article manually:**
```bash
curl -X POST http://127.0.0.1:8000/api/context/track \
  -H "Content-Type: application/json" \
  -d '{
    "trove_id": "12345",
    "title": "Gold Discoveries",
    "date": "1895-05-18",
    "source": "Sydney Morning Herald",
    "url": "https://trove.nla.gov.au/...",
    "snippet": "Reports of gold discoveries..."
  }'
```

### **Get packed context:**
```bash
curl http://127.0.0.1:8000/api/context/pack?max_chars=1000
```

### **List all articles:**
```bash
curl http://127.0.0.1:8000/api/context
```

---

## 💡 Best Practices

1. **Pin key sources** - They'll always be cited first
2. **Use `/cite` command** - Quick way to pin from chat
3. **Check context** - Visit `/api/context` to see what's tracked
4. **Clear when done** - `DELETE /api/context` to start fresh
5. **Stable sessions** - Use `X-Session-Id` header for continuity

---

## 🔧 Configuration

**Environment Variables:**
- `CONTEXT_DB` - Database path (default: `app/data/context.db`)
- `CONTEXT_MAX_PER_SESSION` - Max articles (default: 50)
- `AI_ENABLED` - Enable AI chat (default: false)
- `OPENAI_API_KEY` - Required for AI features

---

## 📈 What's Next?

- ✅ SQLite persistence
- ✅ Pin/unpin UI
- ✅ `/cite` command
- ✅ Auto-tracking
- 🔜 Context search/filter
- 🔜 Timeline view from context
- 🔜 Export context to CSV
- 🔜 Multi-session support

---

**The app is now production-ready with persistent research memory!** 🎉

