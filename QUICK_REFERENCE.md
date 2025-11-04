# 🚀 Quick Reference Card

**Your one-page guide to Trove Research Platform**

## 🎯 Start Here

```bash
bash run.sh
# Then open: http://127.0.0.1:8000/dashboard
```

## 📍 Essential URLs

| What | URL |
|------|-----|
| **Home** | `/dashboard` |
| **Search** | `/search` |
| **Read Article** | `/reader?id=...` |
| **AI Chat** | `/chat` or `/desk` |
| **Collections** | `/collections` |
| **Reports** | `/studio` |
| **Timeline** | `/timeline` |
| **Status** | `/status` |

## ⚡ Quick Actions

- **Search**: Press `/` key or go to `/search`
- **Help**: Press `?` key or click "Help" in sidebar
- **Pin Article**: Click 📌 button on any article
- **View Context**: Go to `/chat` → Click "📚 Research" button

## 🔄 Standard Workflow

```
Dashboard → Search → Click Article → Pin Important → Chat → Export
```

## 📊 Data Locations

- **Database**: `app/data/context.db` (your tracked articles)
- **Reports**: `outputs/` folder
- **Queries**: `queries/trove_queries.csv`

## 🎓 Key Concepts

1. **Auto-tracking**: Articles saved automatically when you click them
2. **Pinning**: Click 📌 to mark articles for AI citation
3. **Context**: AI uses your tracked articles automatically
4. **Persistence**: Everything saved to SQLite

## 🔗 Full Documentation

See `VISION.md` for complete architecture and workflows.

