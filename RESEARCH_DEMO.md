# 🕵️ Research Demo - Full Feature Walkthrough

## ✅ What's Working

### 1. Enhanced Previews
**Location:** `templates/search.html` - Preview drawer now shows:
- ✅ Full metadata (date, issued, source, publisher, newspaper, category, format)
- ✅ Page numbers, volume, place, location
- ✅ Contributors, authors, creators
- ✅ Subjects, keywords, language
- ✅ Trove ID and URLs
- ✅ Description, summary, snippet, full text preview (first 1000 chars)
- ✅ All action buttons (Pin, Read Aloud, Open Reader, Add to Collection, View on Trove)

### 2. Search & Discovery
- ✅ **3,355 results** for "gold discoveries NSW 1850"
- ✅ Filters working (year range, place, publication, format)
- ✅ Result cards with pin buttons (📌) on each
- ✅ Preview drawer opens on click
- ✅ Auto-tracking when articles are viewed

### 3. Context Tracking
- ✅ **Auto-tracking** - Articles automatically saved when viewed
- ✅ **Pin/Unpin** - Pin important articles for citation
- ✅ **Research counter** - Shows "📚 Research (1)" in chat (auto-updates)
- ✅ **Persistence** - All data saved to SQLite (`app/data/context.db`)
- ✅ **Session management** - Tracks by IP+User-Agent (or X-Session-Id header)

### 4. Chat Integration
- ✅ **Context-aware** - Chat knows what you've read
- ✅ **Packed context** - AI receives compact bibliography-style context
- ✅ **Pinned first** - Important articles prioritized
- ✅ **Token limits** - Context capped at 3,500 chars (configurable)

### 5. Read Aloud Features
- ✅ **Text-to-Speech** - 🔊 button on result cards
- ✅ **Preview TTS** - 🔊 button in preview drawer
- ✅ **Reader TTS** - 🔊 Listen button in reader with speed controls
- ✅ **Space bar shortcut** - Press Space to read aloud in preview/reader
- ✅ **Smart text extraction** - Strips metadata labels, reads clean content

## 📊 Current Database State

```bash
# Total articles tracked
Total: 7 articles
Pinned: 2 articles
Sessions: 4 active sessions

# Recent articles
- N.S.W. Gold Discoveries (1851-05-15, The Sydney Morning Herald) - Pinned ✅
- THE GOLD DISCOVERY (1851-05-24, The Argus)
- Gold Discoveries in NSW (1850-03-15, Sydney Morning Herald) - Pinned ✅
- Gold Rush in Bathurst (1851-06-20, The Sydney Gazette)
```

## 🎯 Live Demo Workflow

### Step 1: Search
```
Visit: http://127.0.0.1:8000/search?q=gold+discoveries+NSW+1850
Result: 3,355 matching articles
```

### Step 2: Explore Articles
1. Click any result card → Preview drawer opens with **full details**
2. Click 🔊 Read Aloud → Text-to-speech reads the article
3. Click 📌 Pin → Article pinned for AI citation
4. Click 📖 Open Reader → Full article reader opens

### Step 3: View Context
```
Visit: http://127.0.0.1:8000/chat
Click: 📚 Research (X) button
See: All tracked articles, pinned first
```

### Step 4: Chat with Context
```
Ask: "What articles have I read about gold discoveries?"
AI: Uses packed context to answer with citations
```

## 🔧 Technical Details

### Preview Enhancement
The preview now displays **all available metadata** from the API response:
- Date fields (date, issued)
- Source fields (source, publisher_or_source, newspaper)
- Classification (category, format, page, volume)
- Location (place, l_place)
- Authorship (contributor, author, creator)
- Subject (subject, keywords)
- Technical (trove_id, id, language, views, relevance)
- Content (description, summary, snippet, text preview)

### Read Aloud Improvements
- Smart text extraction (removes UI elements, metadata labels)
- Full article content in preview drawer
- Speed controls in reader (0.5x - 2.0x)
- Keyboard shortcuts (Space bar)

### Context Packing
- Pinned articles first
- Then by recency (last_seen)
- Character limit: 3,500 (configurable)
- Format: Bibliography-style with title, date, source, snippet, URL

## 🎬 Try It Now

1. **Search**: http://127.0.0.1:8000/search?q=gold+discoveries
2. **Click** any article → See detailed preview
3. **Pin** important ones → Check 📚 Research counter
4. **Chat**: http://127.0.0.1:8000/chat → Ask about your research
5. **Listen**: Click 🔊 buttons to hear articles read aloud

Everything is working! 🎉

