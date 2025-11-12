# Entity Extraction & Timeline Features - Installation Guide

## 📦 Required Dependencies

```bash
# Install Python packages
pip install spacy wikipedia

# Download spaCy English model
python -m spacy download en_core_web_sm
```

## ✅ What's Included

### Backend
- **Entity Extraction** (`app/nlp/entity_extract.py`)
  - Extracts PERSON, ORG, GPE, LOC, EVENT, FAC, PRODUCT entities
  - Optional Wikipedia links
  - Graceful fallback if spaCy not installed

- **API Endpoints**
  - `GET /api/entities` - Extract entities from tracked articles
  - `GET /api/timeline?q=term` - Get timeline of mentions for a term

### Frontend
- **Notebook Page** (`/notebook`)
  - Entity sidebar with clickable buttons
  - Timeline charts using Chart.js
  - Responsive design

## 🚀 Usage

1. Track some articles (via search or reader)
2. Visit `/notebook`
3. Click an entity to see its timeline
4. View mentions over time in interactive chart
5. Select multiple entities and click "Compare Selected" to compare timelines
6. Click a bar in the timeline to see articles from that year

## 💬 Chat Integration

Ask questions in chat:
- "extract all people mentioned in 1915 Gallipoli articles"
- "when was X mentioned most?"
- "compare X vs Y"
- "show articles about X from 1926"

Entities are automatically rendered in chat messages with clickable badges.

## 🔧 Optional Features

- Wikipedia links: Install `wikipedia` package
- Entity extraction: Install `spacy` and download model

Without these, the app still works but with reduced functionality.
