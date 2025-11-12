# Verification Checklist - Three Pillars

## ✅ Preflight Complete
- [x] Dependencies installed: trafilatura, readability-lxml, httpx, lxml
- [x] Virtual environment activated

## 1. Reader Full-Text Chain

### Endpoints Created:
- ✅ `/api/reader/text?id=...` - Full text with fallback chain

### Fallback Chain:
1. Trove `articleText` (primary)
2. Scrape with `trafilatura` (fallback 1)
3. Scrape with `readability-lxml` (fallback 2)
4. Trove `snippet` (last resort)

### Test:
```bash
# Replace {id} with a Trove article ID like 16163218
curl -sS "http://127.0.0.1:8000/api/reader/text?id=16163218" | jq .
```

**Expected Response:**
```json
{
  "id": "16163218",
  "source": "trove_articleText" | "scrape_fallback" | "snippet",
  "text": "...",
  "url": "..." (if scrape_fallback)
}
```

### HTML Reader:
```bash
curl -sS "http://127.0.0.1:8000/reader?id=16163218" | head -n 30
```

**Expected:** Full article text displayed, not just snippet.

---

## 2. Search Summarizer

### Endpoint Created:
- ✅ `POST /api/summarize` - Compress search results into bullets

### Test:
```bash
curl -sS -X POST http://127.0.0.1:8000/api/summarize \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [
      {"title": "Test", "date": "1924-08-16", "snippet": "Lower Clarence River deputation ..."},
      {"title": "Another", "date": "1925-01-03", "snippet": "Road works ..."}
    ]
  }' | jq .
```

**Expected Response:**
```json
{
  "bullets": "1924-08-16: Lower Clarence River deputation ... • 1925-01-03: Road works ..."
}
```

**Requirements:**
- 5-8 concise bullets
- ≤800 chars total
- Preserves dates/names
- Truncates long snippets to 160 chars

---

## 3. Thumbnails/IIIF & Context Tray

### Thumbnails:
- ✅ Client-side handling in `search.html` with graceful fallback
- ✅ Thumbnail URLs extracted from Trove records
- ✅ Error handling with placeholder fallback

### Context Tray:
- ✅ Syntax verified: `node -c app/static/js/context-tray.js` passed
- ✅ File location: `backend/app/static/js/context-tray.js`

### Test:
```bash
# Check search page loads without console errors
# Open: http://127.0.0.1:8000/search?q=Iluka%20mining
# Check browser DevTools console for errors
```

**Expected:** No `context-tray.js:234` syntax errors.

---

## Files Created/Modified

### New Files:
- ✅ `backend/app/services/extract_fulltext.py` - Text extraction utilities
- ✅ `backend/app/routers/reader_text.py` - Reader text endpoint
- ✅ `backend/app/routers/summarize.py` - Summarizer endpoint

### Modified Files:
- ✅ `backend/app/main.py` - Added router includes

---

## Quick Test Script

```bash
#!/bin/bash
# Quick verification script

BASE="http://127.0.0.1:8000"

echo "1. Testing Reader Text Endpoint..."
curl -sS "$BASE/api/reader/text?id=16163218" | jq -r '.source' || echo "FAILED"

echo "2. Testing Summarizer..."
curl -sS -X POST "$BASE/api/summarize" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"title":"Test","date":"1924","snippet":"Test snippet"}]}' \
  | jq -r '.bullets' || echo "FAILED"

echo "3. Testing Search Page..."
curl -sS -I "$BASE/search?q=test" | head -n 1

echo "Done!"
```

---

## Troubleshooting

### Reader returns 404:
- Check TROVE_API_KEY is set
- Verify article ID is valid
- Check logs for Trove API errors

### Summarizer returns empty:
- Check request format (items array)
- Verify JSON is valid

### Context Tray syntax error:
- File is at: `backend/app/static/js/context-tray.js`
- Syntax verified with `node -c`
- If still errors, check browser cache (hard refresh: Ctrl+Shift+R)

