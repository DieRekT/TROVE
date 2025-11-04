# UI Wiring Check Report

## ✅ What's Properly Wired

### 1. Article Tracking (Search Page)
- ✅ **Pin buttons** on result cards call `togglePin()` → `/api/context/pin/{id}` or `/api/context/unpin/{id}`
- ✅ **Article clicks** automatically call `trackArticle()` → `/api/context/track`
- ✅ **Preview drawer** also tracks articles when opened
- ✅ **Reader page** tracks articles on load and has pin button

**Location:** `templates/search.html` lines 124, 207, 279-297, 300-320

### 2. Article Tracking (Base Template)
- ✅ **Global `trackArticle()` function** sends to `/api/context/track`
- ✅ **Auto-tracks** articles when result cards are viewed (DOMContentLoaded)
- ✅ **Dual storage**: SQLite (primary) + localStorage (backup)

**Location:** `templates/base.html` lines 596-638, 641-657

### 3. Reader Page
- ✅ **Pin button** calls `togglePin()` → `/api/context/pin/{id}`
- ✅ **Auto-tracks** article on page load → `/api/context/track`
- ✅ Extracts article metadata (title, date, source, snippet, URL)

**Location:** `templates/reader.html` lines 25, 120-145, 339-370

### 4. Chat Interface - Context Tray
- ✅ **Context Tray component** (`context-tray.js`) renders Research button with count
- ✅ **Fetches context** from `/api/context` when opened
- ✅ **Pin/unpin** buttons in tray call `/api/context/pin/{id}`
- ✅ **Clear button** calls `/api/context` DELETE
- ✅ **Sorted by pinned first** then by recency

**Location:** `static/context-tray.js` lines 22-38, 40-50, 52-60, 114-185

### 5. Chat Commands
- ✅ `/context` command opens context tray
- ✅ `/cite` command pins and cites articles
- ✅ `/clear` command clears all context
- ✅ Commands call appropriate API endpoints

**Location:** `templates/chat.html` lines 408-455

---

## ⚠️ Issues Found

### 1. Context Tray Not Auto-Updating
**Problem:** The Research button counter doesn't automatically refresh when articles are tracked.

**Current Behavior:**
- Context tray only fetches when explicitly opened (`toggle()`)
- Counter shows stale count until user clicks Research button
- No auto-refresh on page load or after tracking

**Impact:** User sees "📚 Research (0)" even after viewing articles until they click the button.

**Fix Needed:**
```javascript
// In chat.html, after contextTray initialization:
// Auto-fetch context on page load
if (contextTray) {
  contextTray.fetchContext();
}

// Also auto-refresh after article tracking (if on same page)
// This would require tracking events to trigger refresh
```

### 2. No Visual Feedback on Track
**Problem:** No toast/notification when articles are automatically tracked.

**Current Behavior:**
- Articles track silently in background
- User doesn't know if tracking succeeded

**Impact:** Low confidence that system is working.

**Fix Needed:** Add success/error feedback (optional, but improves UX).

---

## 🔧 Recommended Fixes

### Priority 1: Auto-Update Research Counter
```javascript
// In templates/chat.html, after line 219:
if (contextTray) {
  // Fetch on page load
  contextTray.fetchContext();
  
  // Auto-refresh every 30 seconds (optional)
  setInterval(() => {
    if (contextTray.isOpen) {
      contextTray.fetchContext();
    }
  }, 30000);
}
```

### Priority 2: Update Counter After Tracking
If tracking happens on the same page (e.g., from search results), trigger refresh:
```javascript
// In base.html, after trackArticle success:
fetch('/api/context/track', {...})
  .then(() => {
    // If context tray exists, refresh it
    if (window.contextTray) {
      window.contextTray.fetchContext();
    }
  });
```

---

## ✅ Summary

**Overall Status:** 🟢 **85% Wired**

- All API endpoints are properly called
- Pin/unpin functionality works
- Tracking works automatically
- Context tray displays correctly when opened
- **Missing:** Auto-refresh of counter on page load

**Quick Fix:** Add `contextTray.fetchContext()` call after initialization in `chat.html` to show correct count immediately.

