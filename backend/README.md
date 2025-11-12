# Archive Detective Backend

Production-grade FastAPI backend for deep research and batch processing of Trove archives.

## 🚀 Quick Start

```bash
# 1. Setup environment
./setup.sh

# 2. Configure API key
# Edit .env and set TROVE_API_KEY=your_key_here

# 3. Run server
./run.sh

# Server runs on http://127.0.0.1:8000
```

## 📋 Prerequisites

- Python 3.9+
- TROVE_API_KEY from https://trove.nla.gov.au/about/create-something/using-api/

## 🔧 Setup

```bash
# Install dependencies
./setup.sh

# Configure environment
cp .env.example .env
# Edit .env and set TROVE_API_KEY
```

## 🏃 Running

```bash
# Start server
./run.sh

# Or manually:
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 🧪 Testing

```bash
# Run smoke tests
./smoke.sh

# This will:
# 1. Start server
# 2. Start a batch research job
# 3. Poll until complete
# 4. Fetch report, markdown, evidence
# 5. Run validator
# 6. Check assertions
```

## 📡 API Endpoints

### Deep Research

- `POST /api/research/deep` - Immediate deep research (smaller runs)
- `POST /api/research/deep/stream` - Streaming deep research (SSE)

### Batch Research

- `POST /api/research/start-batch` - Start background batch job
- `GET /api/research/job/{job_id}` - Get job status
- `GET /api/research/job/{job_id}/report` - Get verified report JSON
- `GET /api/research/job/{job_id}/markdown` - Get report as Markdown
- `GET /api/research/job/{job_id}/evidence` - Get evidence as JSONL

### Search & Reader

- `GET /search?q=...` - Search page with results
- `GET /reader?id=...` - Article reader page
- `GET /research?seed=...` - Deep research page

### Dashboard

- `GET /dashboard` - Dashboard HTML
- `GET /api/dashboard` - Dashboard JSON

### Other

- `GET /search?q=...` - Search API (JSON)
- `POST /api/tts/stream` - TTS endpoint (501 Not Implemented stub)

## 📊 Database

SQLite database (`troveing.sqlite`) with:
- `jobs` - Batch research jobs
- `sources` - Ingested Trove articles
- `sources_fts` - FTS5 full-text search index

## 🔍 Example: Iluka Research

```bash
# Start batch job
curl -X POST http://127.0.0.1:8000/api/research/start-batch \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Iluka mineral sands rutile zircon (Clarence River, NSW)",
    "years_from": 1945,
    "years_to": 1980,
    "max_pages": 12,
    "page_size": 100,
    "state": "New South Wales"
  }'

# Get job ID from response, then:
JOB_ID="your-job-id"

# Check status
curl http://127.0.0.1:8000/api/research/job/$JOB_ID

# Get report (when done)
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/report > report.json

# Get markdown
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/markdown > report.md

# Get evidence
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/evidence > evidence.jsonl

# Validate
python3 validate_report.py report.json
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── db.py                # SQLite + FTS5
│   ├── routers/             # API routes
│   │   ├── deep_research.py
│   │   ├── batch_research.py
│   │   ├── dashboard.py
│   │   ├── formatting.py
│   │   └── search_reader.py
│   ├── services/            # Business logic
│   │   ├── deep_research.py
│   │   ├── trove_batch.py
│   │   ├── trove_client.py
│   │   └── stats.py
│   ├── models/              # Pydantic models
│   ├── templates/           # Jinja2 templates
│   └── static/              # Static files
├── setup.sh                 # Setup script
├── run.sh                   # Run script
├── smoke.sh                 # Smoke tests
├── validate_report.py       # Report validator
├── .env.example             # Environment template
└── requirements.txt         # Dependencies
```

## 🔑 Environment Variables

See `.env.example` for all options. Required:
- `TROVE_API_KEY` - Your Trove API key

Optional:
- `TROVEING_DB` - Database path (default: `troveing.sqlite`)
- `WEB_SEARCH_ENABLED` - Enable web search (default: `0`)
- `ALLOWED_ORIGINS` - CORS origins (comma-separated)

## 🐛 Troubleshooting

### Server won't start
- Check `TROVE_API_KEY` is set in `.env`
- Check port 8000 is not in use: `lsof -i :8000`
- Check logs: `tail -f /tmp/troveing_server.log`

### Batch jobs fail
- Check Trove API key is valid
- Check network connectivity
- Review job error: `GET /api/research/job/{job_id}`

### Validator fails
- Ensure report has sources: `jq '.sources | length' report.json`
- Check evidence quotes ≤240 chars
- Verify citations resolve to sources

## 📝 Logs

- Server logs: `/tmp/troveing_server.log` (when run via smoke.sh)
- Database: `troveing.sqlite` (SQLite WAL mode)

## 🎯 Features

- ✅ Deep research with LLM synthesis
- ✅ Batch ingestion with SQLite FTS5
- ✅ BM25 ranking (normalized 0..1)
- ✅ Sentence-level evidence extraction
- ✅ State disambiguation (NSW vs WA)
- ✅ Verified reports (citations must resolve)
- ✅ Markdown/JSONL export
- ✅ Live metrics dashboard
- ✅ Automated validation

## 📚 Documentation

- `BATCH_RESEARCH_README.md` - Batch research details
- `validate_report.py` - Report validation logic

