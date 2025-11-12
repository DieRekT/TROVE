#!/usr/bin/env python3
"""Apply topic guard, BM25 improvements, and make search deeper."""
from pathlib import Path
import re
import json
import textwrap

def W(p, s):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")
    print(f"WROTE {p}")

def P(p, pat, rep, flags=0):
    p = Path(p)
    if not p.exists():
        print(f"SKIP: {p} not found")
        return
    t = p.read_text(encoding="utf-8")
    n = re.sub(pat, rep, t, flags=flags)
    if n != t:
        p.write_text(n, encoding="utf-8")
        print(f"PATCHED {p}")
    else:
        print(f"OK {p} (no change)")

# === 1) Add topic guard to deep_research.py ===
dr = Path("app/services/deep_research.py")
if dr.exists():
    t = dr.read_text(encoding="utf-8")
    
    # Add topic regexes and function before SENT_SPLIT
    if "_is_on_topic" not in t:
        t = t.replace(
            "SENT_SPLIT = re.compile(r\"(?<=[.!?])\\s+\")",
            textwrap.dedent("""
TOPIC_MINE = re.compile(r'\\b(mine|mining|mineral|lease|ilmenite|rutile|zircon|sand|sands|beach|placer|dredg)\\b', re.I)
TOPIC_GEO = re.compile(r'\\b(Iluka|Yamba|Clarence River|Angourie|Woody Head|Shark Bay)\\b', re.I)

def _is_on_topic(title: str, snippet: str, text: str) -> bool:
    blob = " ".join([title or "", snippet or "", text or ""])
    return bool(TOPIC_MINE.search(blob)) and bool(TOPIC_GEO.search(blob))

SENT_SPLIT = re.compile(r"(?<=[.!?])\\s+")
""")
        )
        
        # Add topic guard where SourceItem is created
        t = re.sub(
            r"(sources\.append\(SourceItem\()",
            r"on_topic = _is_on_topic(title, rec.get('snippet') or '', full)\n            if not on_topic:\n                dropped += 1\n                continue\n            sources.append(SourceItem(",
            t
        )
        
        # Initialize dropped counter
        t = t.replace(
            "raw = TroveClient.extract_hits(payload)\n        raw_trove_count = len(raw)",
            "raw = TroveClient.extract_hits(payload)\n        raw_trove_count = len(raw)\n        dropped = 0"
        )
        
        # Update stats to include dropped_offtopic
        t = re.sub(
            r'stats=\{"retrieved": len\(raw\), "used": len\(sources_sorted\), "tokens_in": 0, "tokens_out": 0\}',
            r'stats={"retrieved": len(raw), "used": len(sources_sorted), "dropped_offtopic": dropped, "tokens_in": 0, "tokens_out": 0}',
            t
        )
        
        dr.write_text(t, encoding="utf-8")
        print(f"PATCHED {dr} (topic guard + dropped counter)")
    else:
        print(f"OK {dr} (topic guard already present)")

# === 2) Make search deeper - fetch multiple pages ===
if dr.exists():
    t = dr.read_text(encoding="utf-8")
    
    # Modify to fetch multiple pages based on depth
    if "async def run_deep_research" in t and "pages_to_fetch" not in t:
        # Calculate pages based on depth and max_sources
        t = t.replace(
            "    terms = _terms(req.query)\n    sources: List[SourceItem] = []\n    raw_trove_count = 0",
            textwrap.dedent("""
    terms = _terms(req.query)
    sources: List[SourceItem] = []
    raw_trove_count = 0
    
    # Calculate how many pages to fetch based on depth
    # Standard: 1 page (20 results), Deep: 5 pages (100 results), Brief: 1 page
    pages_to_fetch = {
        "brief": 1,
        "standard": 2,
        "deep": 5
    }.get(req.depth or "standard", 2)
    
    # Increase max_sources for deep searches
    effective_max = req.max_sources
    if req.depth == "deep":
        effective_max = max(req.max_sources, 50)  # At least 50 for deep
    elif req.depth == "standard":
        effective_max = max(req.max_sources, 30)  # At least 30 for standard
""")
        )
        
        # Replace single search with paginated search
        old_search = r"""# Try with year filters first, but if no results, try without year filters
        payload = await trove\.search\(
            q=req\.query,
            n=req\.max_sources,
            year_from=req\.years_from,
            year_to=req\.years_to,
            reclevel="brief",
            include="",
            state=inferred_state
        )
        raw = TroveClient\.extract_hits\(payload\)
        raw_trove_count = len\(raw\)
        
        # If no results with year filter, try without year filter \(year filter might be too restrictive\)
        if raw_trove_count == 0 and \(req\.years_from or req\.years_to\):
            logger\.info\(f"No results with year filter {req\.years_from}-{req\.years_to}, trying without year filter"\)
            payload = await trove\.search\(
                q=req\.query,
                n=req\.max_sources,
                year_from=None,
                year_to=None,
                reclevel="brief",
                include="",
                state=inferred_state
            \)
            raw = TroveClient\.extract_hits\(payload\)
            raw_trove_count = len\(raw\)"""
        
        new_search = textwrap.dedent("""
        # Fetch multiple pages for deeper search
        raw = []
        page_size = 20  # Trove API max per page
        for page in range(pages_to_fetch):
            offset = page * page_size
            try:
                payload = await trove.search(
                    q=req.query,
                    n=page_size,
                    offset=offset,
                    year_from=req.years_from if page == 0 else None,  # Only filter on first page
                    year_to=req.years_to if page == 0 else None,
                    reclevel="brief",
                    include="",
                    state=inferred_state
                )
                page_results = TroveClient.extract_hits(payload)
                raw.extend(page_results)
                if len(page_results) < page_size:
                    break  # No more results
            except Exception as e:
                logger.warning(f"Failed to fetch page {page + 1}: {e}")
                break
        
        raw_trove_count = len(raw)
        
        # If no results with year filter, try without year filter (year filter might be too restrictive)
        if raw_trove_count == 0 and (req.years_from or req.years_to):
            logger.info(f"No results with year filter {req.years_from}-{req.years_to}, trying without year filter")
            raw = []
            for page in range(pages_to_fetch):
                offset = page * page_size
                try:
                    payload = await trove.search(
                        q=req.query,
                        n=page_size,
                        offset=offset,
                        year_from=None,
                        year_to=None,
                        reclevel="brief",
                        include="",
                        state=inferred_state
                    )
                    page_results = TroveClient.extract_hits(payload)
                    raw.extend(page_results)
                    if len(page_results) < page_size:
                        break
                except Exception as e:
                    logger.warning(f"Failed to fetch page {page + 1}: {e}")
                    break
            raw_trove_count = len(raw)""")
        
        t = re.sub(old_search, new_search, t, flags=re.MULTILINE | re.DOTALL)
        
        # Limit to effective_max sources after filtering
        t = t.replace(
            "sources_sorted = sorted(sources, key=lambda s: s.relevance, reverse=True)",
            "sources_sorted = sorted(sources, key=lambda s: s.relevance, reverse=True)[:effective_max]"
        )
        
        dr.write_text(t, encoding="utf-8")
        print(f"PATCHED {dr} (deeper search with pagination)")

# === 3) BM25 normalization & de-dup for batch_research ===
br = Path("app/routers/batch_research.py")
if br.exists():
    t = br.read_text(encoding="utf-8")
    
    # Add de-dup function
    if "_norm_title" not in t:
        t = t.replace(
            "from fastapi import APIRouter, HTTPException",
            "from fastapi import APIRouter, HTTPException\nimport re"
        )
        t = t.replace(
            "async def get_report(",
            textwrap.dedent("""
def _norm_title(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    # collapse repeated words
    return re.sub(r'\\b(\\w+)( \\1)+\\b', r'\\1', s)

async def get_report(""")
        )
        
        # Add de-dup after sorting
        if "sources_sorted = sorted" in t and "deduped = []" not in t:
            t = t.replace(
                "sources_sorted = sorted(sources, key=lambda s: s['relevance'], reverse=True)",
                textwrap.dedent("""
sources_sorted = sorted(sources, key=lambda s: s['relevance'], reverse=True)
seen_titles = set()
deduped = []
for s in sources_sorted:
    k = _norm_title(s.get('title', ''))
    if k in seen_titles:
        continue
    seen_titles.add(k)
    deduped.append(s)
sources_sorted = deduped""")
            )
    
    br.write_text(t, encoding="utf-8")
    print(f"PATCHED {br} (BM25 + dedup)")

# === 4) Update samples JSON ===
samples = {
    "samples": [
        {
            "label": "Iluka mineral sands (1945–1980, NSW)",
            "query": "Iluka mineral sands Clarence River NSW Yamba Iluka beach sand rutile zircon ilmenite mining lease dredge",
            "years_from": 1945,
            "years_to": 1980,
            "depth": "deep"
        },
        {
            "label": "Ashby ferry incidents (1900–1925, Harwood/Maclean)",
            "query": "Ashby ferry Harwood Shire Council accident cable punt breakdown Maclean",
            "years_from": 1900,
            "years_to": 1925,
            "depth": "standard"
        },
        {
            "label": "East Clarence gold mining (1890–1935)",
            "query": "East Clarence gold mine Bendigo anticline Paddy's Gully reef",
            "years_from": 1890,
            "years_to": 1935,
            "depth": "standard"
        }
    ]
}
W("app/static/samples/research_samples.json", json.dumps(samples, ensure_ascii=False, indent=2))

# === 5) Add UI drift badge ===
rs = Path("app/static/js/research.js")
if rs.exists():
    js = rs.read_text(encoding="utf-8")
    if "dropped_offtopic" not in js:
        js = js.replace(
            "const report = await postJSON('/api/research/deep', payload);",
            textwrap.dedent("""
const report = await postJSON('/api/research/deep', payload);
// show off-topic drop badge if backend set stats
if (report?.stats?.dropped_offtopic > 0) {
  const progressStatus = document.getElementById('progressStatus');
  if (progressStatus) {
    progressStatus.innerHTML = `✅ Complete (filtered ${report.stats.dropped_offtopic} off-topic hits)`;
    progressStatus.style.color = '#b45309';
  }
}""")
        )
        rs.write_text(js, encoding="utf-8")
        print(f"PATCHED {rs} (drift badge)")

print("\n✅ All patches applied!")

