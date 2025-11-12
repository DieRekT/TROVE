# TROVE Platform Features

## Entity Extraction

### Overview
Extract named entities (people, organizations, places, events) from tracked articles using spaCy NER with optional Wikipedia links.

### Endpoints
- `GET /api/entities` - Extract entities from all tracked articles in the current session
- `POST /api/analysis/extract-entities` - Extract entities from filtered article sets

### Usage
1. Track articles by viewing them in search or reader
2. Visit `/notebook` to see extracted entities
3. Click an entity to view its timeline
4. Compare multiple entities on a timeline chart

### Chat Integration
Ask questions like:
- "extract all people mentioned in 1915 Gallipoli articles"
- "find all organizations from 1940-1950"
- "extract all places mentioned in mining articles"

### Entity Types
- **PERSON** - People mentioned in articles
- **ORG** - Organizations, companies, institutions
- **GPE** - Geopolitical entities (countries, cities)
- **LOC** - Locations (buildings, landmarks)
- **EVENT** - Events, occurrences
- **FAC** - Facilities (airports, buildings)
- **PRODUCT** - Products, items

## Timeline Features

### Overview
Track entity mentions over time with interactive timeline charts. Compare multiple entities on a single timeline.

### Endpoints
- `GET /api/timeline?q=term` - Get timeline of mentions for a search term
- `GET /api/timeline/compare?q=term1,term2` - Compare timeline mentions for multiple terms
- `GET /api/timeline/hits?q=term&year=YYYY` - Get articles matching a term in a specific year

### Usage
1. Track articles by viewing them in search or reader
2. Visit `/notebook` and click an entity to see its timeline
3. Select multiple entities and click "Compare Selected" to compare timelines
4. Click a bar in the timeline chart to see articles from that year

### Chat Integration
Ask questions like:
- "when was X mentioned most?"
- "compare X vs Y"
- "show articles about X from 1926"

### Timeline Page
Visit `/timeline` to see a visual timeline of events. Add custom events, zoom, and filter by year range.

## Structured Reports

### Overview
Generate AI-powered research reports with executive summaries, key findings, timelines, and sources. Uses BM25 ranking and sentence-level quote extraction.

### Endpoints
- `POST /api/research/deep` - Generate deep research report
- `POST /api/research/deep/stream` - Streaming deep research (SSE)

### Request Format
```json
{
  "query": "Iluka mineral sands mining",
  "region": "NSW",
  "years_from": 1940,
  "years_to": 2000,
  "max_sources": 12,
  "depth": "standard"
}
```

### Response Format
```json
{
  "query": "Iluka mineral sands mining",
  "executive_summary": "...",
  "key_findings": [
    {
      "title": "...",
      "insight": "...",
      "evidence": ["quote1", "quote2"],
      "citations": ["TROVE:...", "WEB:..."],
      "confidence": 0.85
    }
  ],
  "timeline": [
    {
      "date": "1945-01-01",
      "event": "...",
      "citations": ["TROVE:..."]
    }
  ],
  "sources": [
    {
      "id": "TROVE:...",
      "title": "...",
      "year": 1945,
      "url": "...",
      "snippets": ["quote1", "quote2"],
      "relevance": 0.95
    }
  ],
  "stats": {
    "retrieved": 100,
    "dropped_offtopic": 20,
    "used": 12
  }
}
```

### Chat Integration
Ask questions like:
- "research Iluka mineral sands mining from 1940 to 2000"
- "generate report on gold discoveries NSW"
- "deep research Clarence River sand mining"

### Report Features
- **Executive Summary** - Concise overview of findings
- **Key Findings** - Structured insights with evidence and citations
- **Timeline** - Chronological events with dates and citations
- **Sources** - Ranked sources with relevance scores and quotes
- **BM25 Ranking** - Relevance-based source ranking
- **Sentence-level Quotes** - Verbatim quotes from sources (≤240 chars)
- **State Filtering** - Filter by region (NSW, WA, etc.)

## Chat Integration

### Overview
Natural language chat interface with entity extraction, timeline visualization, and structured report generation.

### Features
- **Entity Extraction** - Extract entities from tracked articles
- **Timeline Visualization** - Interactive timeline charts in chat
- **Structured Reports** - Generate research reports with executive summaries
- **Article Lists** - Display article lists with links
- **Citations** - Show citations for referenced articles

### Chat Commands
- `/search <query>` - Search Trove archives
- `/read <id>` - Read article by ID
- `/cite <id>` - Pin and cite article
- `/summarize <text>` - Summarize text
- `/generate-queries` - Generate CSV queries
- `/make-brief` - Create brief template
- `/help` - Show all commands

### Natural Language Queries
- "extract all people mentioned in 1915 Gallipoli articles"
- "when was X mentioned most?"
- "compare X vs Y"
- "research Iluka mineral sands mining from 1940 to 2000"
- "summarise Australian coverage of WWII between 1939–1945"

## Notebook Page

### Overview
Interactive notebook for exploring entities, timelines, and research insights.

### Features
- **Entity Sidebar** - List of extracted entities with counts
- **Timeline Charts** - Interactive charts showing entity mentions over time
- **Entity Comparison** - Compare multiple entities on a single timeline
- **Article Lists** - View articles mentioning entities in specific years
- **Entity Selection** - Click entities to select and compare

### Usage
1. Track articles by viewing them in search or reader
2. Visit `/notebook` to see extracted entities
3. Click an entity to view its timeline
4. Select multiple entities and click "Compare Selected"
5. Click a bar in the timeline to see articles from that year

## API Endpoints

### Entity Extraction
- `GET /api/entities` - Extract entities from tracked articles
- `POST /api/analysis/extract-entities` - Extract entities from filtered articles

### Timeline
- `GET /api/timeline?q=term` - Get timeline for a term
- `GET /api/timeline/compare?q=term1,term2` - Compare timelines
- `GET /api/timeline/hits?q=term&year=YYYY` - Get articles for a term/year

### Structured Reports
- `POST /api/research/deep` - Generate research report
- `POST /api/research/deep/stream` - Streaming research report

### Chat
- `POST /api/chat` - Chat endpoint with natural language queries

## Installation

### Dependencies
```bash
pip install spacy wikipedia
python -m spacy download en_core_web_sm
```

### Optional Features
- **spaCy** - Entity extraction (required for entity features)
- **wikipedia** - Wikipedia links for entities (optional)
- **OpenAI** - LLM-powered synthesis and reports (optional)

Without these, the app still works but with reduced functionality.

## Usage Examples

### Entity Extraction
```bash
# Extract entities from tracked articles
curl http://localhost:8000/api/entities

# Extract people from 1915 articles
curl -X POST http://localhost:8000/api/analysis/extract-entities \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "Gallipoli",
    "date_from": "1915",
    "date_to": "1915",
    "entity_types": ["PERSON"]
  }'
```

### Timeline
```bash
# Get timeline for a term
curl http://localhost:8000/api/timeline?q=gold

# Compare multiple terms
curl http://localhost:8000/api/timeline/compare?q=gold,silver

# Get articles for a term/year
curl http://localhost:8000/api/timeline/hits?q=gold&year=1851
```

### Structured Reports
```bash
# Generate research report
curl -X POST http://localhost:8000/api/research/deep \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Iluka mineral sands mining",
    "region": "NSW",
    "years_from": 1940,
    "years_to": 2000,
    "max_sources": 12,
    "depth": "standard"
  }'
```

### Chat
```bash
# Chat with natural language
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "extract all people mentioned in 1915 Gallipoli articles"
  }'
```

## Documentation

- [README.md](README.md) - Main project documentation
- [INSTALL_ENTITIES.md](backend/INSTALL_ENTITIES.md) - Entity extraction installation guide
- [API Documentation](backend/app/routers/) - API endpoint documentation
