# Archive Detective — Phase 2 (Facets + Filter Chips + Term Highlighting)

This drop extends Phase‑1 with:

- **Date range filtering** (`start`, `end`, ISO `YYYY-MM-DD`).
- **Type/category filtering** (Trove categories → `newspaper, article, picture, book, map, music, collection, archive, people, place`).
- **Active filter chips** (removable badges synced to URL).
- **Search‑term highlighting** in result titles/snippets.
- **Matching `/export`** with the same filters.

> Implementation is conservative: types are passed to Trove; dates are additionally filtered server‑side for reliability. All state is URL‑encoded for shareability.

---

## Backend Changes

### `backend/app/adapters/trove.py` (replace)
```python
import os
import orjson
from typing import Any, Dict, List, Optional
from httpx import AsyncClient

# ——— Helpers ———

def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Trove v2/v3 vary; we defensively extract common fields.
    title = raw.get("title") or raw.get("heading") or raw.get("name") or "Untitled"
    date = raw.get("issueDate") or raw.get("date") or raw.get("issued")
    snippet = raw.get("snippet") or raw.get("summary") or raw.get("troveUrl")
    identifier = (
        str(raw.get("id"))
        or raw.get("identifier")
        or raw.get("recordID")
        or (raw.get("work") or {}).get("id")
        or title
    )
    type_ = raw.get("type") or raw.get("category") or raw.get("zone")
    url = raw.get("url") or raw.get("troveUrl") or raw.get("identifier")
    thumb = (
        (raw.get("thumbnail") or raw.get("thumb"))
        or (raw.get("image") or {}).get("thumbnail")
    )
    return {
        "id": identifier,
        "title": title,
        "snippet": snippet,
        "date": date,
        "type": type_,
        "source": "Trove",
        "url": url,
        "thumbnail": thumb,
    }

async def search_trove(
    client: AsyncClient,
    q: str,
    page: int,
    page_size: int,
    types: Optional[str] = None,
) -> Dict[str, Any]:
    """Query Trove v3. `types` is a comma‑separated list of categories.
    Returns { total, items:[NormalizedItem-like dicts] }.
    """
    if os.getenv("TROVE_MOCK", "false").lower() == "true":
        _SAMPLE = {
            "total": 3,
            "items": [
                {
                    "id": "sample-1",
                    "title": "ASHBY. (Daily Examiner, 3 Sep 1918)",
                    "snippet": "Mr. Robt. J. Forrester …",
                    "date": "1918-09-03",
                    "type": "newspaperArticle",
                    "troveUrl": "https://trove.nla.gov.au/…",
                },
                {
                    "id": "sample-2",
                    "title": "Harwood Island – sugar industry photo",
                    "snippet": "Historic photo from Clarence River region.",
                    "date": "1930-01-01",
                    "type": "picture",
                    "troveUrl": "https://trove.nla.gov.au/…",
                },
                {
                    "id": "sample-3",
                    "title": "Shipping movements – Maclean",
                    "snippet": "Notices of departures and arrivals.",
                    "date": "1907-05-14",
                    "type": "newspaperArticle",
                    "troveUrl": "https://trove.nla.gov.au/…",
                },
            ],
        }
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

### `backend/app/main.py` (replace)
```python
import os
import orjson
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from .models import SearchResponse, NormalizedItem
from .schemas import ReadyResponse
from .deps import get_http_client, get_cache
from .adapters.trove import search_trove
from .utils.csv_export import items_to_csv_bytes

app = FastAPI(title="Archive Detective API", version="0.2.0")

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

# ——— helpers ———

def _iso(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    # accept YYYY or YYYY-MM or YYYY-MM-DD
    try:
        if len(date_str) == 4:
            return f"{date_str}-01-01"
        if len(date_str) == 7:
            return f"{date_str}-01"
        if len(date_str) == 10:
            return date_str
    except Exception:
        return None
    return None

def _within(d: Optional[str], start: Optional[str], end: Optional[str]) -> bool:
    if not d:
        return True
    try:
        d_iso = d if len(d) == 10 else _iso(d)
        if not d_iso:
            return True
        if start and d_iso < start:
            return False
        if end and d_iso > end:
            return False
        return True
    except Exception:
        return True

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    types: Optional[str] = Query(None, description="Comma-separated categories (e.g. newspaper,picture)"),
    start: Optional[str] = Query(None, description="Start date YYYY or YYYY-MM or YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY or YYYY-MM or YYYY-MM-DD"),
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

@app.get("/export")
async def export(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    format: str = Query("csv", pattern="^(csv|json)$"),
    types: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    data = await search_trove(client, q=q, page=page, page_size=page_size, types=types)

    start_iso = _iso(start)
    end_iso = _iso(end)

    items = [it for it in data.get("items", []) if _within(it.get("date"), start_iso, end_iso)]

    if format == "json":
        payload = orjson.dumps(items)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=export-{q}.json"},
        )

    # csv
    csv_bytes = items_to_csv_bytes(items)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=export-{q}.csv"},
    )

@app.get("/")
async def root():
    return PlainTextResponse("Archive Detective API. Use /search?q=term")
```

---

## Frontend Additions

### `frontend/lib/api.ts` (replace)
```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000';

export type Item = {
  id: string;
  title: string;
  snippet?: string;
  date?: string;
  type?: string;
  source: string;
  url?: string;
  thumbnail?: string;
}

export type SearchPayload = {
  ok: boolean;
  q: string;
  page: number;
  page_size: number;
  total: number;
  items: Item[];
}

export type SearchOpts = {
  page?: number;
  pageSize?: number;
  types?: string[];     // categories
  start?: string;       // YYYY|YYYY-MM|YYYY-MM-DD
  end?: string;         // YYYY|YYYY-MM|YYYY-MM-DD
}

function withFilters(u: URL, opts?: SearchOpts) {
  if (!opts) return;
  if (opts.page) u.searchParams.set('page', String(opts.page));
  if (opts.pageSize) u.searchParams.set('page_size', String(opts.pageSize));
  if (opts.types?.length) u.searchParams.set('types', opts.types.join(','));
  if (opts.start) u.searchParams.set('start', opts.start);
  if (opts.end) u.searchParams.set('end', opts.end);
}

export async function search(q: string, opts?: SearchOpts): Promise<SearchPayload> {
  const u = new URL(`${API_BASE}/search`);
  u.searchParams.set('q', q);
  withFilters(u, opts);
  const res = await fetch(u.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function exportResults(q: string, format: 'csv' | 'json', opts?: SearchOpts) {
  const u = new URL(`${API_BASE}/export`);
  u.searchParams.set('q', q);
  withFilters(u, opts);
  u.searchParams.set('format', format);
  const res = await fetch(u.toString());
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `export-${q}.${format}`;
  a.click();
}
```

### `frontend/components/Highlight.tsx` (new)
```tsx
import React from 'react';

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export default function Highlight({ text, query }:{ text: string; query: string }) {
  if (!text || !query) return <>{text}</>;
  // Split query into unique terms >1 char
  const terms = Array.from(new Set(
    query
      .split(/\s+/)
      .map(t => t.replace(/^["']|["']$/g, ''))
      .filter(t => t.length > 1)
  ));
  if (!terms.length) return <>{text}</>;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi');
  const parts = text.split(pattern);
  return (
    <span>
      {parts.map((p, i) => (
        pattern.test(p) ? <mark key={i} className="bg-yellow-200 px-0.5">{p}</mark> : <React.Fragment key={i}>{p}</React.Fragment>
      ))}
    </span>
  );
}
```

### `frontend/components/Filters.tsx` (new)
```tsx
'use client';
import { useRouter, useSearchParams } from 'next/navigation';
import { useMemo, useState } from 'react';

const ALL_TYPES = [
  'newspaper','article','picture','book','map','music','collection','archive','people','place'
];

export default function Filters() {
  const router = useRouter();
  const sp = useSearchParams();

  const q = (sp.get('q') || '').trim();
  const start0 = sp.get('start') || '';
  const end0 = sp.get('end') || '';
  const types0 = (sp.get('types') || '').split(',').filter(Boolean);

  const [start, setStart] = useState(start0);
  const [end, setEnd] = useState(end0);
  const [types, setTypes] = useState<string[]>(types0);

  function toggleType(t: string) {
    setTypes(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  }

  function apply() {
    const u = new URL(window.location.href);
    if (q) u.searchParams.set('q', q);
    else u.searchParams.delete('q');
    if (start) u.searchParams.set('start', start); else u.searchParams.delete('start');
    if (end) u.searchParams.set('end', end); else u.searchParams.delete('end');
    if (types.length) u.searchParams.set('types', types.join(',')); else u.searchParams.delete('types');
    router.push(u.pathname + '?' + u.searchParams.toString());
  }

  function clearAll() {
    const u = new URL(window.location.href);
    ['start','end','types'].forEach(k => u.searchParams.delete(k));
    router.push(u.pathname + '?' + u.searchParams.toString());
  }

  return (
    <div className="rounded-lg border bg-white p-3 space-y-3">
      <div className="flex gap-3 items-end">
        <div>
          <label className="block text-xs text-neutral-600">Start date (YYYY or YYYY-MM or YYYY-MM-DD)</label>
          <input className="mt-1 w-48 rounded border px-2 py-1" value={start} onChange={e=>setStart(e.target.value)} placeholder="1910 or 1910-05" />
        </div>
        <div>
          <label className="block text-xs text-neutral-600">End date</label>
          <input className="mt-1 w-48 rounded border px-2 py-1" value={end} onChange={e=>setEnd(e.target.value)} placeholder="1950-12-31" />
        </div>
        <button className="ml-auto rounded bg-blue-600 text-white px-3 py-2 hover:bg-blue-700" onClick={apply}>Apply</button>
        <button className="rounded border px-3 py-2" onClick={clearAll}>Clear</button>
      </div>

      <div>
        <div className="text-xs text-neutral-600 mb-2">Types</div>
        <div className="flex flex-wrap gap-3">
          {ALL_TYPES.map(t => (
            <label key={t} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={types.includes(t)} onChange={()=>toggleType(t)} />
              <span>{t}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### `frontend/components/ActiveChips.tsx` (new)
```tsx
'use client';
import { useRouter, useSearchParams } from 'next/navigation';

function Chip({ label, onRemove }:{ label: string; onRemove: ()=>void }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-neutral-200 px-3 py-1 text-sm">
      {label}
      <button className="text-neutral-600 hover:text-black" onClick={onRemove} aria-label={`Remove ${label}`}>×</button>
    </span>
  );
}

export default function ActiveChips() {
  const router = useRouter();
  const sp = useSearchParams();

  const q = sp.get('q') || '';
  const start = sp.get('start') || '';
  const end = sp.get('end') || '';
  const types = (sp.get('types') || '').split(',').filter(Boolean);

  const chips: { key: string; label: string; remove: () => void }[] = [];

  function dropParam(key: string) {
    const u = new URL(window.location.href);
    u.searchParams.delete(key);
    router.push(u.pathname + '?' + u.searchParams.toString());
  }

  if (start) chips.push({ key: 'start', label: `Start: ${start}`, remove: ()=>dropParam('start') });
  if (end) chips.push({ key: 'end', label: `End: ${end}`, remove: ()=>dropParam('end') });
  types.forEach((t) => {
    chips.push({ key: `type:${t}`, label: `Type: ${t}`, remove: () => {
      const u = new URL(window.location.href);
      const cur = (u.searchParams.get('types') || '').split(',').filter(Boolean);
      const nxt = cur.filter(x => x !== t);
      if (nxt.length) u.searchParams.set('types', nxt.join(',')); else u.searchParams.delete('types');
      router.push(u.pathname + '?' + u.searchParams.toString());
    }});
  });

  if (!chips.length) return null;

  return (
    <div className="flex flex-wrap gap-2">{chips.map((c, i) => <Chip key={`${c.key}:${i}`} label={c.label} onRemove={c.remove} />)}</div>
  );
}
```

### `frontend/components/ResultList.tsx` (replace to add highlighting)
```tsx
import type { Item } from '@/lib/api';
import Highlight from '@/components/Highlight';
import { useSearchParams } from 'next/navigation';

export default function ResultList({ items, total }:{ items: Item[]; total: number }) {
  const sp = useSearchParams();
  const q = (sp.get('q') || '').trim();

  if (!items?.length) return <div className="text-sm text-neutral-500">No results yet.</div>;
  return (
    <div className="space-y-3">
      <div className="text-xs text-neutral-500">Total: {total}</div>
      {items.map((it) => (
        <div key={it.id} className="rounded-lg border p-3 bg-white">
          <div className="font-medium">
            <Highlight text={it.title} query={q} />
          </div>
          {it.snippet && <div className="text-sm text-neutral-700 mt-1"><Highlight text={it.snippet} query={q} /></div>}
          <div className="text-xs text-neutral-500 mt-2 flex gap-3">
            {it.date && <span>{it.date}</span>}
            {it.type && <span>· {it.type}</span>}
            <span>· {it.source}</span>
            {it.url && (
              <a className="text-blue-700 underline" href={it.url} target="_blank">Open source</a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### `frontend/app/page.tsx` (replace to wire filters & exports)
```tsx
'use client';
import { useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import SearchBar from '@/components/SearchBar';
import Filters from '@/components/Filters';
import ActiveChips from '@/components/ActiveChips';
import ResultList from '@/components/ResultList';
import Loading from '@/components/Loading';
import { search as apiSearch, exportResults } from '@/lib/api';

export default function Page() {
  const sp = useSearchParams();
  const q = (sp.get('q') || '').trim();
  const start = sp.get('start') || undefined;
  const end = sp.get('end') || undefined;
  const types = (sp.get('types') || '').split(',').filter(Boolean);

  const opts = useMemo(() => ({ start, end, types }), [start, end, types]);

  const { data, isFetching, error } = useQuery({
    queryKey: ['search', q, start, end, types.sort().join(',')],
    queryFn: () => apiSearch(q, opts),
    enabled: !!q,
  });

  // Keyboard shortcut: e = export CSV with current filters
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() === 'e' && q) {
        e.preventDefault();
        exportResults(q, 'csv', opts);
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [q, opts]);

  return (
    <main className="space-y-6">
      <SearchBar />
      <Filters />
      <ActiveChips />

      <div className="flex gap-2 items-center">
        <button
          disabled={!q}
          className="rounded-lg border px-3 py-2 disabled:opacity-50"
          onClick={() => q && exportResults(q, 'csv', opts)}
        >Export CSV (e)</button>
        <button
          disabled={!q}
          className="rounded-lg border px-3 py-2 disabled:opacity-50"
          onClick={() => q && exportResults(q, 'json', opts)}
        >Export JSON</button>
        {isFetching && <Loading />}
      </div>

      {error && <div className="text-red-700">{String((error as Error).message)}</div>}

      <ResultList items={data?.items || []} total={data?.total || 0} />
    </main>
  );
}
```

---

## README Addendum (Phase‑2)

Append to `README.md`:

```md
## Phase‑2 features
- Date range filtering via URL params: `start`, `end` (YYYY|YYYY-MM|YYYY-MM-DD)
- Type/category filtering via `types=newspaper,picture,...`
- Active filter chips (click × to remove), state lives in URL
- Query term highlighting in titles/snippets
- `/export` honors the same filters

### Example URLs
- `/?q=Harwood%20Island&types=newspaper,picture&start=1900&end=1950`

### Backend notes
- Types are passed to Trove `category` param.
- Date range is additionally filtered server‑side for reliability across shapes.
```

---

## Update Commands (Ubuntu)

```bash
cd ~/Projects/archive-detective

# Backend: replace files per this drop
# (Use Cursor to overwrite the files listed above.)

# Restart backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend: install new deps if any (none added), restart dev server
cd ../frontend
npm run dev
```

---

## Quick Test

1) Open: `http://localhost:3000/?q=Harwood%20Island&types=newspaper,picture&start=1900&end=1950`
2) Confirm chips render. Click × to remove one.
3) Confirm highlighting for words like `Harwood` and `Island`.
4) Click **Export CSV**; verify the file name and filters are respected.

If anything breaks, paste the full backend trace and the browser console log. I'll patch with minimal churn.

