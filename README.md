# TROVE Deep Research Platform

AI-powered search, summarization, and analysis of historical newspaper archives using Trove API v3, OpenAI, and modern tooling.

## 🔍 Features

- Semantic search over Trove (multi-page fetch, BM25 ranking, NSW bias)
- Sentence-level quote extraction with verified citations (TROVE:IDs)
- "Deep Research" reports: Executive Summary, Findings, Timeline, Sources
- Reader with scrape fallback if articleText/snippet is missing
- Context pinning + summarization; Markdown / JSONL exports
- Lightweight cache + topic guard to reduce noise and API calls
- **Entity Extraction** - Extract people, organizations, places, events from articles (spaCy NER)
- **Timeline Visualization** - Track entity mentions over time with interactive charts
- **Chat Integration** - Natural language queries with entity extraction, timeline, and report generation
- **Structured Reports** - AI-powered research reports with executive summaries, findings, and timelines

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python 3.10/3.11, SQLite + FTS5 (BM25)
- **Frontend:** Jinja2 templates, Tailwind, Vanilla JS, Chart.js
- **AI:** OpenAI (optional for synthesis), spaCy (NER with Wikipedia links)
- **Infra:** ngrok (optional), Cursor IDE, GitHub Actions (validator)

## 🚀 Quick Start

```bash
git clone https://github.com/DieRekT/TROVE.git
cd TROVE
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add:
# TROVE_API_KEY=your_trove_v3_key
# (optional) OPENAI_API_KEY=sk-...

# Run the server
uvicorn app.main:app --reload --port 8000
```

Then open: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)

## 🌐 Public Tunnel (optional)

```bash
ngrok http 8000
```

## 📦 Project Structure

```
TROVE/
├── app/                # Backend logic (APIs, NLP, context)
├── templates/          # Jinja HTML views
├── static/             # JS, CSS
├── data/               # (Optional) static Trove/JSONL dumps
├── outputs/            # Research summaries and reports
├── requirements.txt
└── app/main.py
```

## 📄 License

MIT — Open source and open research.
