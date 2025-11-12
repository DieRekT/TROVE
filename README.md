# TROVE Deep Research Platform

AI-powered search, summarization, and analysis of historical newspaper archives using Trove API, OpenAI, and modern tooling.

## 🔍 Features

- Semantic search over Trove articles
- Full-text scraping (fallback if snippet missing)
- Context pinning + summarization
- Timeline-based entity comparison
- Chat assistant with archive awareness
- Report Studio for exportable summaries
- Entity/NER extraction and deep analysis

## 🛠️ Tech Stack

- **Backend**: FastAPI, SQLite, Python 3.11
- **Frontend**: HTML, Tailwind, Vanilla JS, Chart.js
- **AI**: OpenAI (LLM), spaCy (NER), BM25 (search)
- **Infra**: ngrok, Cursor IDE, GitHub

## 🚀 Getting Started

```bash
git clone https://github.com/DieRekT/TROVE.git
cd TROVE
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
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
├── notebooks/          # Output research summaries
├── requirements.txt
├── ngrok.yml
└── main.py
```

## 📄 License

MIT — Open source and open research.
