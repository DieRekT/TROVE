# Archive Detective — Phase 4

Adds a **faceted side panel**, **IIIF manifest proxy/minifier**, and **multi‑page streaming exports**. Back‑compatible with Phase‑1; if you already applied Phase‑2/3, this drop aligns with that shape (filters, details panel, etc.).

---

## Backend changes (FastAPI)

### 1) `backend/app/adapters/trove.py` — extend signature (types pass‑through)
```python
# ... existing imports
from typing import Any, Dict, List, Optional

# keep _normalize_item and _SAMPLE as in Phase‑1

async def search_trove(client: AsyncClient, q: str, page: int, page_size: int, types: Optional[str] = None) -> Dict[str, Any]:
    if os.getenv("TROVE_MOCK", "false").lower() == "true":
        start = (page - 1) * page_size
        end = start + page_size
        items = _SAMPLE["items"][start:end]
        return {"total": _SAMPLE["total"], "items": [_normalize_item(x) for x in items]}

    base = os.getenv("TROVE_BASE_URL", "https://api.trove.nla.gov.au/v3")
    key = os.getenv("TROVE_API_KEY")
    if not key:
        raise ValueError("TROVE_API_KEY is not set; or enable TROVE_MOCK=true for offline dev")

    start = max(0, (page - 1) * page_size)
    url = f"{base}/result"
    category = types or "newspaper,article,picture,book,map,music,collection,archive,people,place"
    params = {
        "q": q,
        "category": category,
        "encoding": "json",
        "n": str(page_size),
        "s": str(start),
        "key": key,
        "include": "workVersions,links,people,places",
    }

    r = await client.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    items: List[Dict[str, Any]] = []
    total = 0
    if isinstance(data, dict):
        total = int(data.get("total", 0)) if str(data.get("total", "0")).isdigit() else 0
        raw_items = data.get("items") or data.get("results") or data.get("work") or []
        for x in raw_items:
            try:
                items.append(_normalize_item(x))
            except Exception:
                continue
    return {"total": total or len(items), "items": items}
```

### 2) `backend/app/utils/streaming.py` — new (CSV/JSON streaming helpers)
```python
from __future__ import annotations
import csv, io, json
from typing import AsyncIterable, Dict, Iterable

async def stream_csv(rows: AsyncIterable[Dict[str, object]], headers: Iterable[str]):
    # write header once, then per-row
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(headers), extrasaction="ignore")
    writer.writeheader()
    yield out.getvalue().encode("utf-8"); out.seek(0); out.truncate(0)
    async for row in rows:
        writer.writerow(row)
        yield out.getvalue().encode("utf-8"); out.seek(0); out.truncate(0)

async def stream_json_array(objs: AsyncIterable[Dict[str, object]]):
    first = True
    yield b"["
    async for obj in objs:
        chunk = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if first:
            yield chunk; first = False
        else:
            yield b"," + chunk
    yield b"]"
```

### 3) `backend/app/main.py` — extend search (types,+optional date window), add `/facets`, `/export/stream`, and IIIF proxy/minifier
```python
import os, orjson, json
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator
from fastapi import FastAPI, Query, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from .models import SearchResponse, NormalizedItem
from .schemas import ReadyResponse
from .deps import get_http_client, get_cache
from .adapters.trove import search_trove
from .utils.csv_export import items_to_csv_bytes
from .utils.streaming import stream_csv, stream_json_array

app = FastAPI(title="Archive Detective API", version="0.4.0")

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ready", response_model=ReadyResponse)
async def ready(cache=Depends(get_cache)):
    return ReadyResponse(ok=True, cache=cache.backend_name())

# —— helpers ——

def _iso(date_str: Optional[str]) -> Optional[str]:
    if not date_str: return None
    try:
        if len(date_str) == 4 and date_str.isdigit():
            return f"{date_str}-01-01"
        if len(date_str) == 7:
            datetime.strptime(date_str, "%Y-%m"); return f"{date_str}-01"
        if len(date_str) == 10:
            datetime.strptime(date_str, "%Y-%m-%d"); return date_str
    except Exception:
        return None
    return None

def _within(d: Optional[str], start: Optional[str], end: Optional[str]) -> bool:
    if not d: return True
    d_iso = d if len(d) == 10 else _iso(d)
    if not d_iso: return True
    if start and d_iso < start: return False
    if end and d_iso > end: return False
    return True

def _year(d: Optional[str]) -> Optional[int]:
    if not d: return None
    try:
        if len(d) >= 4 and d[:4].isdigit():
            return int(d[:4])
    except Exception:
        return None
    return None

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    types: Optional[str] = Query(None, description="Comma-separated categories (e.g. newspaper,picture)"),
    start: Optional[str] = Query(None, description="Start date YYYY|YYYY-MM|YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY|YYYY-MM|YYYY-MM-DD"),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    cache_key = f"trove:{q}:{page}:{page_size}:{types}:{start}:{end}"
    cached = await cache.get(cache_key)
    if cached:
        data = orjson.loads(cached)
        return SearchResponse(**data)

    try:
        data = await search_trove(client, q=q, page=page, page_size=page_size, types=types)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    start_iso = _iso(start)
    end_iso = _iso(end)
    items = [it for it in data.get("items", []) if _within(it.get("date"), start_iso, end_iso)]
    resp = SearchResponse(
        q=q,
        page=page,
        page_size=page_size,
        total=len(items) if (start_iso or end_iso) else int(data.get("total", len(items))),
        items=[NormalizedItem(**it) for it in items],
    )
    await cache.set(cache_key, orjson.dumps(resp.model_dump()).decode("utf-8"))
    return resp

@app.get("/facets")
async def facets(
    q: str = Query(..., min_length=1),
    types: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    facet_pages: int = Query(2, ge=1, le=5),
    page_size: int = Query(50, ge=10, le=100),
    client=Depends(get_http_client),
):
    start_iso, end_iso = _iso(start), _iso(end)
    type_counts: Dict[str, int] = {}
    year_counts: Dict[int, int] = {}
    total = 0
    for p in range(1, facet_pages + 1):
        data = await search_trove(client, q=q, page=p, page_size=page_size, types=types)
        for it in data.get("items", []):
            if not _within(it.get("date"), start_iso, end_iso):
                continue
            t = (it.get("type") or "unknown").lower()
            type_counts[t] = type_counts.get(t, 0) + 1
            y = _year(it.get("date"))
            if y: year_counts[y] = year_counts.get(y, 0) + 1
            total += 1
    # return compact JSON
    return JSONResponse({
        "ok": True,
        "q": q,
        "considered": total,
        "type_counts": type_counts,
        "year_counts": year_counts,
        "start": start,
        "end": end,
    })

@app.get("/export/stream")
async def export_stream(
    q: str = Query(..., min_length=1),
    format: str = Query("csv", pattern="^(csv|json)$"),
    types: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    pages: int = Query(5, ge=1, le=100),
    page_size: int = Query(200, ge=10, le=200),
    client=Depends(get_http_client),
):
    start_iso, end_iso = _iso(start), _iso(end)

    async def row_stream() -> AsyncGenerator[Dict[str, Any], None]:
        for p in range(1, pages + 1):
            data = await search_trove(client, q=q, page=p, page_size=page_size, types=types)
            for it in data.get("items", []):
                if _within(it.get("date"), start_iso, end_iso):
                    yield it

    filename = f"export-{q}"
    if format == "json":
        return StreamingResponse(stream_json_array(row_stream()), media_type="application/json", headers={
            "Content-Disposition": f"attachment; filename={filename}.json"
        })
    # CSV
    headers = ["id","title","snippet","date","type","source","url","thumbnail"]
    return StreamingResponse(stream_csv(row_stream(), headers), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename={filename}.csv"
    })

# —— IIIF proxy/minifier ——
@app.get("/iiif/proxy")
async def iiif_proxy(src: str = Query(..., description="Remote IIIF manifest URL"), client=Depends(get_http_client)):
    allow = os.getenv("IIIF_PROXY_ALLOWLIST", "").strip()
    if allow:
        ok = any(host and host in src for host in allow.split(","))
        if not ok:
            raise HTTPException(status_code=400, detail="Blocked by IIIF proxy allowlist")
    r = await client.get(src, timeout=30.0)
    r.raise_for_status()
    data = r.content
    return StreamingResponse(iter([data]), media_type="application/json")

@app.post("/iiif/minify")
async def iiif_minify(item: NormalizedItem = Body(...)):
    # minimal IIIF v3 manifest for a single image/canvas if thumbnail is usable
    img = item.thumbnail or item.url
    if not img:
        raise HTTPException(status_code=400, detail="No image URL on item")
    mid = f"urn:ad:{item.id}"
    manifest = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{mid}/manifest",
        "type": "Manifest",
        "label": {"en": [item.title or "Untitled"]},
        "items": [
            {
                "id": f"{mid}/canvas/1",
                "type": "Canvas",
                "height": 800,
                "width": 800,
                "items": [
                    {
                        "id": f"{mid}/page/1/1",
                        "type": "AnnotationPage",
                        "items": [
                            {
                                "id": f"{mid}/annotation/1",
                                "type": "Annotation",
                                "motivation": "painting",
                                "body": {"id": img, "type": "Image"},
                                "target": f"{mid}/canvas/1",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    payload = orjson.dumps(manifest)
    return StreamingResponse(iter([payload]), media_type="application/json")

@app.get("/")
async def root():
    return PlainTextResponse("Archive Detective API. Use /search?q=term")
```

> No new pip dependencies required.

---

## Frontend changes (Next.js App Router)

### 1) `frontend/lib/api.ts` — add filters and streaming export URL helper
```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000';

export type Item = { id: string; title: string; snippet?: string; date?: string; type?: string; source: string; url?: string; thumbnail?: string; };
export type SearchPayload = { ok: boolean; q: string; page: number; page_size: number; total: number; items: Item[] };
export type SearchOpts = { page?: number; pageSize?: number; types?: string[]; start?: string; end?: string };

function withFilters(u: URL, opts?: SearchOpts) {
  if (!opts) return;
  if (opts.page) u.searchParams.set('page', String(opts.page));
  if (opts.pageSize) u.searchParams.set('page_size', String(opts.pageSize));
  if (opts.types?.length) u.searchParams.set('types', opts.types.join(','));
  if (opts.start) u.searchParams.set('start', opts.start);
  if (opts.end) u.searchParams.set('end', opts.end);
}

export async function search(q: string, opts?: SearchOpts): Promise<SearchPayload> {
  const u = new URL(`${API_BASE}/search`); u.searchParams.set('q', q); withFilters(u, opts);
  const res = await fetch(u.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`); return res.json();
}

export function exportStreamURL(q: string, format: 'csv'|'json', opts?: SearchOpts & { pages?: number; pageSize?: number; }) {
  const u = new URL(`${API_BASE}/export/stream`);
  u.searchParams.set('q', q); u.searchParams.set('format', format);
  if (opts?.pages) u.searchParams.set('pages', String(opts.pages));
  if (opts?.pageSize) u.searchParams.set('page_size', String(opts.pageSize));
  withFilters(u, opts); return u.toString();
}

export async function getFacets(q: string, opts?: { types?: string[]; start?: string; end?: string; facetPages?: number }) {
  const u = new URL(`${API_BASE}/facets`); u.searchParams.set('q', q);
  if (opts?.types?.length) u.searchParams.set('types', opts.types.join(','));
  if (opts?.start) u.searchParams.set('start', opts.start);
  if (opts?.end) u.searchParams.set('end', opts.end);
  if (opts?.facetPages) u.searchParams.set('facet_pages', String(opts.facetPages));
  const res = await fetch(u.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`Facets failed: ${res.status}`); return res.json();
}
```

### 2) `frontend/components/FacetPanel.tsx` — new
```tsx
'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getFacets } from '@/lib/api';

const ALL_TYPES = ['newspaper','article','picture','book','map','music','collection','archive','people','place'];

export default function FacetPanel() {
  const sp = useSearchParams(); const router = useRouter();
  const q = (sp.get('q') || '').trim();
  const start0 = sp.get('start') || ''; const end0 = sp.get('end') || '';
  const types0 = (sp.get('types') || '').split(',').filter(Boolean);
  const [types, setTypes] = useState<string[]>(types0);
  const [start, setStart] = useState(start0); const [end, setEnd] = useState(end0);
  const [facets, setFacets] = useState<any>(null);

  useEffect(() => { (async () => { if (!q) return setFacets(null); try { setFacets(await getFacets(q, { types, start, end, facetPages: 2 })); } catch { setFacets(null); } })(); }, [q, types.join(','), start, end]);

  function toggleType(t: string) { setTypes(prev => prev.includes(t) ? prev.filter(x=>x!==t) : [...prev, t]); }
  function apply() { const u = new URL(window.location.href); if (q) u.searchParams.set('q', q); else u.searchParams.delete('q');
    if (types.length) u.searchParams.set('types', types.join(',')); else u.searchParams.delete('types');
    if (start) u.searchParams.set('start', start); else u.searchParams.delete('start');
    if (end) u.searchParams.set('end', end); else u.searchParams.delete('end');
    router.push(u.pathname + '?' + u.searchParams.toString()); }

  return (
    <aside className="space-y-4">
      <div className="rounded-lg border bg-white p-3">
        <div className="text-sm font-medium mb-2">Date</div>
        <div className="space-y-2">
          <input className="w-full rounded border px-2 py-1" placeholder="Start (YYYY or YYYY-MM or YYYY-MM-DD)" value={start} onChange={e=>setStart(e.target.value)} />
          <input className="w-full rounded border px-2 py-1" placeholder="End" value={end} onChange={e=>setEnd(e.target.value)} />
          <button className="w-full rounded bg-blue-600 text-white px-3 py-2" onClick={apply}>Apply</button>
        </div>
      </div>

      <div className="rounded-lg border bg-white p-3">
        <div className="text-sm font-medium mb-2">Types</div>
        <div className="flex flex-col gap-1 max-h-72 overflow-auto pr-1">
          {ALL_TYPES.map(t => (
            <label key={t} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={types.includes(t)} onChange={()=>toggleType(t)} />
              <span className="flex-1">{t}</span>
              <span className="text-xs text-neutral-500">
                {facets?.type_counts?.[t] ?? 0}
              </span>
            </label>
          ))}
        </div>
      </div>

      {facets?.year_counts && (
        <div className="rounded-lg border bg-white p-3">
          <div className="text-sm font-medium mb-2">Years (sampled)</div>
          <div className="space-y-1 max-h-56 overflow-auto">
            {Object.entries(facets.year_counts).sort((a:any,b:any)=>Number(a[0])-Number(b[0])).map(([y,c]: any) => (
              <div key={y} className="flex items-center gap-2 text-xs">
                <div className="w-14 text-right">{y}</div>
                <div className="h-2 bg-neutral-200 rounded flex-1">
                  <div className="h-2 bg-neutral-600 rounded" style={{ width: `${Math.min(100, (c/Math.max(1, Math.max(...Object.values(facets.year_counts))))*100)}%` }} />
                </div>
                <div className="w-10 text-right">{c}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
```

### 3) `frontend/app/page.tsx` — wire side panel + streaming export button
```tsx
'use client';
import { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import SearchBar from '@/components/SearchBar';
import ResultList from '@/components/ResultList';
import Loading from '@/components/Loading';
import FacetPanel from '@/components/FacetPanel';
import { search as apiSearch, exportStreamURL } from '@/lib/api';

export default function Page() {
  const sp = useSearchParams();
  const q = (sp.get('q') || '').trim();
  const start = sp.get('start') || undefined;
  const end = sp.get('end') || undefined;
  const types = (sp.get('types') || '').split(',').filter(Boolean);
  const opts = useMemo(() => ({ start, end, types }), [start, end, types]);

  const { data, isFetching, error } = useQuery({ queryKey: ['search', q, start, end, types.sort().join(',')], queryFn: () => apiSearch(q, opts), enabled: !!q });

  useEffect(() => { function onKey(e: KeyboardEvent) { if (e.key.toLowerCase() === 'e' && q) { e.preventDefault(); window.location.href = exportStreamURL(q, 'csv', { ...opts, pages: 5, pageSize: 200 }); } } document.addEventListener('keydown', onKey); return () => document.removeEventListener('keydown', onKey); }, [q, opts]);

  return (
    <main className="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div className="md:col-span-1">
        <SearchBar />
        <div className="mt-4"><FacetPanel /></div>
      </div>
      <div className="md:col-span-3 space-y-4">
        <div className="flex gap-2 items-center">
          <a className="rounded-lg border px-3 py-2 disabled:opacity-50" aria-disabled={!q} href={q ? exportStreamURL(q, 'csv', { ...opts, pages: 5, pageSize: 200 }) : undefined}>Export CSV (multi‑page)</a>
          <a className="rounded-lg border px-3 py-2 disabled:opacity-50" aria-disabled={!q} href={q ? exportStreamURL(q, 'json', { ...opts, pages: 5, pageSize: 200 }) : undefined}>Export JSON (multi‑page)</a>
          {isFetching && <Loading />}
        </div>
        {error && <div className="text-red-700">{String((error as Error).message)}</div>}
        <ResultList items={data?.items || []} total={data?.total || 0} />
      </div>
    </main>
  );
}
```

> If you already have a Details modal (Phase‑3), no change needed here; the list props remain compatible.

---

## README Addendum (Phase‑4)

Append to `README.md`:

```md
## Phase‑4
- **Facets**: `/facets?q=…&types=…&start=…&end=…&facet_pages=2` returns `type_counts` and `year_counts` (sampled across first N pages).
- **Streaming Export**: `/export/stream?q=…&format=csv|json&pages=N&page_size=M` iterates multiple pages and streams a single file.
- **IIIF**: `/iiif/proxy?src=<manifest-url>` (allowlist via `IIIF_PROXY_ALLOWLIST`), `/iiif/minify` builds a minimal IIIF v3 Manifest from a `NormalizedItem`.

### Example
- Stream 5 pages × 200 results → CSV: `/export/stream?q=Harwood&format=csv&pages=5&page_size=200`.
- Facets for newspapers 1900–1950: `/facets?q=Harwood&types=newspaper&start=1900&end=1950`.
```

---

## Commands (Ubuntu)

```bash
# Backend
cd ~/Projects/archive-detective/backend
# Update adapters/trove.py, add utils/streaming.py, and replace app/main.py per Phase‑4
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend
cd ../frontend
# Add FacetPanel.tsx and update lib/api.ts + app/page.tsx per Phase‑4
npm run dev
```

## Quick test
1) Open `http://localhost:3000/?q=Harwood` — confirm results.
2) Use **Facets**: tick `newspaper`, set `start=1900`, `end=1950`, **Apply** → URL updates and results reflect filters.
3) Click **Export CSV (multi‑page)** — you should get a streaming download that includes multiple pages.
4) (Optional) Call `GET /iiif/proxy?src=<manifest>` in the browser or `POST /iiif/minify` with a JSON item that has a `thumbnail` to retrieve a minimal Manifest.

If anything throws, paste the full backend traceback and the browser console log. I’ll patch with zero churn.

