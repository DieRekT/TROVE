# 🚀 Quick Start Guide - See Everything Working

## Step-by-Step Instructions

### 1️⃣ **Search for Articles**
```
Type in search box: "gold discoveries NSW 1850"
Press Enter or click 🔍 Search
```
**Expected:** You'll see ~3,355 results

### 2️⃣ **Click Any Article**
```
Click on any result card (e.g., "SCIENCE for the PEOPLE Geology Helped By Gold Discoveries")
```
**Expected:** 
- Preview drawer opens on the right
- Shows detailed metadata (date, source, snippet, etc.)
- Action buttons appear (📌 Pin, 🔊 Read Aloud, 📖 Open Reader)

### 3️⃣ **Test Read Aloud**
```
In the preview drawer, click the 🔊 "Read Aloud" button
```
**Expected:** Browser text-to-speech reads the article content

### 4️⃣ **Pin an Article**
```
Click the 📌 "Pin" button in the preview drawer
```
**Expected:** 
- Button changes to show pinned state
- Article is saved to your research context
- Toast notification: "Pinned for citation"

### 5️⃣ **Open Full Reader**
```
Click 📖 "Open Reader" button
```
**Expected:** 
- Full article reader opens
- Left side: Full text with 🔊 Listen button
- Right side: Original scan (if available)
- Pin button in header

### 6️⃣ **Check Research Context**
```
Navigate to: http://127.0.0.1:8000/chat
Look for: "📚 Research (X)" button at bottom
Click: The Research button
```
**Expected:**
- Context tray opens showing all tracked articles
- Pinned articles appear first
- Each article shows: title, date, source, snippet
- Pin/unpin buttons on each article

### 7️⃣ **Ask AI About Your Research**
```
In chat, type: "What articles have I read about gold discoveries?"
Press Send
```
**Expected:**
- AI responds using your research context
- References the articles you've viewed
- Provides citations based on tracked articles

## 🎯 What to Type for Best Results

### Search Queries That Work Well:
1. `"gold discoveries NSW 1850"` - Historical gold rush
2. `"Sydney Morning Herald" AND "gold"` - Specific newspaper
3. `"Bathurst" AND "gold"` - Location-based
4. `"Hargraves"` - Person search
5. `"gold rush" AND date:[1850 TO 1852]` - Date range

### Chat Questions to Try:
- `"What articles have I read about gold discoveries?"`
- `"Summarize the articles I've pinned"`
- `"Compare the dates of my gold discovery articles"`
- `"/context"` - Opens context tray
- `"/cite"` - Shows pinned articles for citation

## 📊 What You Should See

### After Clicking 3-4 Articles:
- **Research counter**: "📚 Research (3)" or higher
- **Context tray**: Shows all articles, pinned first
- **Database**: Articles saved to `app/data/context.db`

### Preview Drawer Shows:
- ✅ Title (large, prominent)
- ✅ Date (📅 1851-05-15)
- ✅ Source (📰 The Sydney Morning Herald)
- ✅ Category, Format, Page, Volume
- ✅ Place/Location
- ✅ Author/Contributor (if available)
- ✅ Subject/Keywords
- ✅ Full snippet
- ✅ Text preview (first 1000 chars if available)
- ✅ All action buttons

### Reader Page Shows:
- ✅ Full article text (left side)
- ✅ Original scan image (right side, if available)
- ✅ 🔊 Listen button with speed controls
- ✅ Pin button in header
- ✅ Explain, Define, Translate buttons
- ✅ Zoom controls for scan

## 🔍 Pro Tips

1. **Use filters** - Narrow by year, place, publication
2. **Pin strategically** - Pin articles you want AI to cite
3. **Read aloud** - Great for long articles while multitasking
4. **Check context** - Click 📚 Research to see what's tracked
5. **Use `/cite`** - Get formatted citations for pinned articles

## 🎤 Read Aloud Features

- **Space bar** - Press Space in preview/reader to toggle read aloud
- **Speed control** - Adjust 0.5x to 2.0x in reader
- **Smart extraction** - Automatically removes UI elements, reads clean content

## ✅ Verification Checklist

After following steps above, verify:
- [ ] Search returns results
- [ ] Preview drawer opens with details
- [ ] Read aloud works (hear voice)
- [ ] Pin button toggles (shows ✅ when pinned)
- [ ] Research counter shows number > 0
- [ ] Context tray shows tracked articles
- [ ] Chat can reference your research

Everything working? You're all set! 🎉

