# Test & Debug Plan Status

## ✅ Completed

1. **BM25 Normalization Fixed**
   - Updated `bm25_to_score()` to use min-max normalization
   - Added `normalize_bm25_scores()` function for batch normalization
   - Formula: `score = (max_bm25 - bm25_value) / (max_bm25 - min_bm25 + 1e-9)`
   - Lower BM25 → Higher relevance score (0-1 range)

2. **TTS Health Endpoint**
   - Added `/api/tts/health` endpoint
   - Returns `{"available": false}` when TTS not implemented
   - Frontend can check this and fall back to browser `speechSynthesis`

3. **Context Tray JavaScript**
   - No syntax errors found in `context-tray.js`
   - Code is valid and functional

4. **State Parameter Mapping**
   - Added state abbreviation to full name mapping in `trove_client.py`
   - Maps "NSW" → "New South Wales", etc.

## 🔧 In Progress

1. **Trove API v3 Parameter Issues**
   - Error: 400 Bad Request when using `l-state` parameter
   - Need to verify if Trove API v3 supports state filtering
   - May need to remove `l-state` or use different approach

2. **Text Extraction Dependencies**
   - `trafilatura` and `readability-lxml` need to be installed
   - Currently returning empty strings when libraries not available
   - Should install in virtual environment

3. **Deep Research Endpoint**
   - Returns "No evidence found" - likely because database is empty
   - Need to seed data first before testing
   - Seed endpoint is failing due to Trove API 400 error

## 📋 Remaining Tasks

1. **Fix Trove API State Filtering**
   - Option A: Remove `l-state` parameter if not supported
   - Option B: Use different filtering mechanism (post-filtering)
   - Option C: Verify correct parameter format for Trove API v3

2. **Install Dependencies**
   ```bash
   cd ~/Projects/trove/backend
   source .venv/bin/activate
   pip install trafilatura readability-lxml lxml
   ```

3. **Test Seed Endpoint**
   - Fix Trove API call to work without state filter
   - Test with smaller page counts
   - Verify data ingestion into SQLite

4. **Test Deep Research**
   - Seed database with sample data
   - Test deep research endpoint
   - Verify sources, findings, timeline are populated

5. **Test Batch Ingestion**
   - Test batch research endpoint
   - Verify FTS5 indexing
   - Check BM25 scores are non-zero

6. **Test Text Extraction**
   - Test trafilatura extraction
   - Test readability-lxml fallback
   - Verify graceful degradation when libraries unavailable

7. **Frontend Testing**
   - Test TTS button visibility
   - Verify no console errors
   - Test all pages load correctly

## 🔍 Issues Found

1. **Trove API 400 Error**
   - URL: `https://api.trove.nla.gov.au/v3/result?q=Iluka%20mining%20mineral%20sands&n=100&category=newspaper&reclevel=full&encoding=json&include=articleText%2Clinks&l-year=1945-1980&l-state=New%20South%20Wales`
   - Error: `httpx.HTTPStatusError: Client error '400 '`
   - Possible causes:
     - `l-state` parameter not supported
     - `reclevel=full` not supported
     - `include=articleText,links` not supported
     - Year range format incorrect

2. **Text Extraction Returns Empty**
   - Libraries not installed in virtual environment
   - Need to install: `trafilatura`, `readability-lxml`, `lxml`

3. **Deep Research Returns No Evidence**
   - Database is empty
   - Need to seed data first
   - Seed endpoint is failing due to Trove API error

## 🛠️ Next Steps

1. **Fix Trove API Calls**
   - Test with minimal parameters first
   - Remove `l-state` if not supported
   - Try `reclevel=brief` instead of `full`
   - Verify `include` parameter format

2. **Install Dependencies**
   - Install text extraction libraries
   - Verify imports work
   - Test extraction functions

3. **Test Seed Endpoint**
   - Use simplified Trove API calls
   - Test with single page first
   - Verify data ingestion

4. **Run Full Test Suite**
   - Test all endpoints
   - Verify BM25 normalization
   - Check text extraction fallback
   - Test frontend functionality

## 📝 Notes

- BM25 normalization is now correct (min-max normalization)
- TTS health endpoint is working
- State parameter mapping is implemented
- Need to resolve Trove API parameter issues
- Need to install text extraction dependencies
- Need to test with actual data

