# Batch Research System

Production-grade batch research system with SQLite FTS5 indexing, background jobs, and verified reports.

## Features

- **Batch Trove ingestion** with paged results (handles hundreds/thousands of articles)
- **SQLite FTS5** full-text search index for fast evidence retrieval
- **Background jobs** with async processing (prevents ngrok timeouts)
- **Verified reports** - citations must exist in indexed sources (no phantom cites)
- **Exports** - Markdown and JSONL formats

## Quick Start

### 1. Start a Batch Job

```bash
curl -X POST http://127.0.0.1:8000/api/research/start-batch \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Iluka mineral sands rutile zircon (Clarence River, NSW)",
    "years_from": 1945,
    "years_to": 1980,
    "max_pages": 15,
    "page_size": 100
  }' | jq
```

Response:
```json
{
  "job_id": "abc-123-def-456",
  "status": "queued"
}
```

### 2. Check Job Status

```bash
JOB_ID="abc-123-def-456"  # from step 1
curl http://127.0.0.1:8000/api/research/job/$JOB_ID | jq
```

Status values:
- `queued` - Job is waiting to start
- `running` - Job is actively ingesting data
- `done` - Job completed successfully
- `error` - Job failed (check `error` field)

### 3. Get Verified Report

Once status is `done`:

```bash
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/report?max_sources=20 | jq
```

The report includes:
- `executive_summary` - Overview of findings
- `key_findings` - Evidence-backed findings with citations
- `timeline` - Chronological events from sources
- `sources` - All indexed sources with relevance snippets
- `stats` - Usage statistics

### 4. Export Reports

**Markdown export:**
```bash
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/markdown -o report.md
```

**JSONL evidence export:**
```bash
curl http://127.0.0.1:8000/api/research/job/$JOB_ID/evidence -o evidence.jsonl
```

## Architecture

### Database Schema

- **`jobs`** table - Tracks batch ingestion jobs
- **`sources`** table - Stores Trove articles with metadata
- **`sources_fts`** - FTS5 full-text search index

### Background Processing

Jobs run asynchronously using `asyncio.create_task()`, so:
- API returns immediately with `job_id`
- No blocking/timeouts on large ingestions
- Progress tracked in database

### Verified Synthesis

- Reports only cite sources that exist in the database
- Evidence snippets extracted from actual article text
- Timeline built from publication years in indexed sources
- No phantom citations or empty evidence sets

## API Endpoints

### POST `/api/research/start-batch`

Start a new batch ingestion job.

**Request body:**
```json
{
  "query": "search terms",
  "years_from": 1945,      // optional
  "years_to": 1980,        // optional
  "max_pages": 15,         // max pages to fetch
  "page_size": 100,        // results per page
  "max_sources_for_report": 20  // optional, for report generation
}
```

### GET `/api/research/job/{job_id}`

Get job status and metadata.

### GET `/api/research/job/{job_id}/report`

Generate verified report from indexed evidence.

**Query params:**
- `max_sources` (default: 20) - Maximum sources to include

### GET `/api/research/job/{job_id}/markdown`

Export report as Markdown.

### GET `/api/research/job/{job_id}/evidence`

Export evidence as JSONL (one source per line).

## Database Location

Default: `troveing.sqlite` in the current working directory.

Override with environment variable:
```bash
export TROVEING_DB=/path/to/custom.db
```

## Troubleshooting

### Job stuck in "queued" or "running"

- Check server logs for errors
- Verify `TROVE_API_KEY` is set
- Check database file permissions

### No evidence found (422 error)

- Verify job status is `done`
- Check that sources were actually ingested (query `sources` table)
- Try widening year range or adjusting query terms

### FTS search returns no results

- Ensure FTS index is populated (check `sources_fts` table)
- Verify query terms are not too restrictive
- Try simpler query terms

## Next Steps

- **Ranking improvements** - BM25 scoring, recency boosts, field weighting
- **State scoping** - Auto-detect and prefer relevant states (e.g., NSW for Clarence River)
- **NER extraction** - Named entity recognition for places, organizations, topics
- **Cross-archive support** - Add other datasets alongside Trove
- **LLM synthesis** - Use structured outputs for better report generation

