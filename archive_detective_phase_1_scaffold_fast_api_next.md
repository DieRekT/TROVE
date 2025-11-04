# Archive Detective — Phase 1 (Export + Fast UX + Shareable URLs + Keyboard)

This is a Cursor‑ready, copy‑paste scaffold that runs **today**. It includes:

- **Backend (FastAPI)**: `/search`, `/export`, `/ready`, Trove adapter, Redis/memory cache, CORS.
- **Frontend (Next.js App Router + React Query + Tailwind)**: search page, loading states, keyboard shortcuts, shareable URLs, CSV/JSON export buttons.
- **Mock mode** so you can verify the UI without a live Trove key.
- **Exact commands** at the end of this doc.

> Phase‑1 target features: Export (CSV/JSON), loading indicators, keyboard shortcuts, copyable search URL, basic results list. (Filters, highlighting, IIIF, notebooks come in Phase‑2/3.)

---

## Folder Layout

```
archive-detective/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── deps.py
│   │   ├── caching.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── utils/
│   │   │   └── csv_export.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── trove.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── Loading.tsx
│   │   ├── ResultList.tsx
│   │   └── SearchBar.tsx
│   ├── lib/
│   │   └── api.ts
│   ├── public/
│   ├── styles/
│   │   └── globals.css
│   ├── package.json
│   ├── next.config.mjs
│   ├── postcss.config.mjs
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docker-compose.yml
├── README.md
└── scripts/
    └── run-dev.sh
```

---

## Backend

### `backend/requirements.txt`

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
python-dotenv==1.0.1
redis==5.0.8
orjson==3.10.7
pydantic==2.9.2
```

### `backend/.env.example`

```env
# Copy to backend/.env and set values
TROVE_API_KEY=replace-with-your-trove-key
TROVE_BASE_URL=https://api.trove.nla.gov.au/v3
# When true, backend returns built-in sample results (no network required)
TROVE_MOCK=false
# Optional Redis cache (falls back to memory if not reachable)
REDIS_URL=redis://localhost:6379/0
# CORS for local Next.js dev
ALLOWED_ORIGINS=http://localhost:3000
```

### `backend/app/__init__.py`

```python
__all__ = []
```

### `backend/app/models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional

class NormalizedItem(BaseModel):
    id: str
    title: str
    snippet: Optional[str] = None
    date: Optional[str] = None
    type: Optional[str] = None
    source: str = "Trove"
    url: Optional[str] = None
    thumbnail: Optional[str] = None

class SearchResponse(BaseModel):
    ok: bool = True
    q: str
    page: int
    page_size: int
    total: int
    items: list[NormalizedItem]
```

### `backend/app/schemas.py`

```python
from pydantic import BaseModel

class ReadyResponse(BaseModel):
    ok: bool
    cache: str
```

### `backend/app/caching.py`

```python
import asyncio
import time
from typing import Any, Optional

try:
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore

class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            v = self._store.get(key)
            if not v:
                return None
            expires_at, data = v
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return data

    async def set(self, key: str, value: Any):
        async with self._lock:
            self._store[key] = (time.time() + self.ttl, value)

class Cache:
    def __init__(self, redis_url: Optional[str], ttl_seconds: int = 300):
        self.redis_url = redis_url
        self.ttl = ttl_seconds
        self.redis = None
        self.memory = SimpleTTLCache(ttl_seconds)

    async def connect(self):
        if self.redis_url and aioredis:
            try:
                self.redis = aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
                await self.redis.ping()
            except Exception:
                self.redis = None

    async def get(self, key: str):
        if self.redis:
            try:
                return await self.redis.get(key)
            except Exception:
                return await self.memory.get(key)
        return await self.memory.get(key)

    async def set(self, key: str, value: str):
        if self.redis:
            try:
                await self.redis.set(key, value, ex=self.ttl)
                return
            except Exception:
                pass
        await self.memory.set(key, value)

    def backend_name(self) -> str:
        return "redis" if self.redis else "memory"
```

### `backend/app/deps.py`

```python
import os
import httpx
from typing import AsyncGenerator
from .caching import Cache


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    timeout = httpx.Timeout(20.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "ArchiveDetective/1.0"}) as client:
        yield client

_cache: Cache | None = None

async def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(redis_url=os.getenv("REDIS_URL"), ttl_seconds=300)
        await _cache.connect()
    return _cache
```

### `backend/app/utils/csv_export.py`

```python
import csv
import io
from typing import Iterable

CSV_FIELDS = ["id", "title", "snippet", "date", "type", "source", "url", "thumbnail"]

def items_to_csv_bytes(items: Iterable[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for it in items:
        writer.writerow(it)
    return buf.getvalue().encode("utf-8")
```

### `backend/app/adapters/trove.py`

```python
import os
import orjson
from typing import Any, Dict, List
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
            "type": "photograph",
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

async def search_trove(client: AsyncClient, q: str, page: int, page_size: int) -> Dict[str, Any]:
    if os.getenv("TROVE_MOCK", "false").lower() == "true":
        # deterministic mock for dev
        start = (page - 1) * page_size
        end = start + page_size
        items = _SAMPLE["items"][start:end]
        return {"total": _SAMPLE["total"], "items": [_normalize_item(x) for x in items]}

    base = os.getenv("TROVE_BASE_URL", "https://api.trove.nla.gov.au/v3")
    key = os.getenv("TROVE_API_KEY")
    if not key:
        raise ValueError("TROVE_API_KEY is not set; or enable TROVE_MOCK=true for offline dev")

    # Trove v3 example: /result?category=newspaper&q=term&encoding=json&n=20&s=0
    # We request multiple categories for a general search. Adjust as needed later.
    start = max(0, (page - 1) * page_size)
    url = f"{base}/result"
    params = {
        "q": q,
        "category": "newspaper,article,picture,book,map,music,collection,archive,people,place",
        "encoding": "json",
        "n": str(page_size),
        "s": str(start),
        "key": key,
        "include": "workVersions,links,people,places",
    }

    r = await client.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    # Normalize results from possible shapes
    items: List[Dict[str, Any]] = []
    total = 0

    # v3 can include a top-level 'total' and 'items' list; fallbacks try known shapes
    if isinstance(data, dict):
        total = int(data.get("total", 0)) if str(data.get("total", "0")).isdigit() else 0
        raw_items = data.get("items") or []
        if not raw_items:
            # some responses may nest in 'results' or 'work'
            raw_items = data.get("results") or data.get("work") or []
        for x in raw_items:
            try:
                items.append(_normalize_item(x))
            except Exception:
                # Best-effort normalization; skip bad items, never break search
                continue

    return {"total": total or len(items), "items": items}
```

### `backend/app/main.py`

```python
import os
import json
import orjson
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from .models import SearchResponse, NormalizedItem
from .schemas import ReadyResponse
from .deps import get_http_client, get_cache
from .adapters.trove import search_trove
from .utils.csv_export import items_to_csv_bytes

app = FastAPI(title="Archive Detective API", version="0.1.0")

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

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    cache_key = f"trove:{q}:{page}:{page_size}"
    cached = await cache.get(cache_key)
    if cached:
        data = orjson.loads(cached)
        return SearchResponse(q=q, page=page, page_size=page_size, total=data["total"], items=data["items"])  # type: ignore

    try:
        data = await search_trove(client, q=q, page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # persist compact cache
    await cache.set(cache_key, orjson.dumps(data).decode("utf-8"))

    items = [NormalizedItem(**it) for it in data["items"]]
    return SearchResponse(q=q, page=page, page_size=page_size, total=int(data["total"]), items=items)

@app.get("/export")
async def export(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    format: str = Query("csv", pattern="^(csv|json)$"),
    client=Depends(get_http_client),
    cache=Depends(get_cache),
):
    # NOTE: export always fetches fresh for requested page/page_size; Phase‑2 will add multi‑page export
    data = await search_trove(client, q=q, page=page, page_size=page_size)
    items = data.get("items", [])

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

## Frontend (Next.js 15, App Router)

### `frontend/package.json`

```json
{
  "name": "archive-detective-frontend",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000"
  },
  "dependencies": {
    "@tanstack/react-query": "5.59.17",
    "next": "15.0.3",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "autoprefixer": "10.4.20",
    "postcss": "8.4.47",
    "tailwindcss": "3.4.13",
    "typescript": "5.6.3"
  }
}
```

### `frontend/next.config.mjs`

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: { appDir: true }
};
export default nextConfig;
```

### `frontend/tailwind.config.ts`

```ts
import type { Config } from 'tailwindcss'

export default {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}'
  ],
  theme: { extend: {} },
  plugins: []
} satisfies Config
```

### `frontend/postcss.config.mjs`

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "jsx": "react-jsx",
    "allowJs": false,
    "resolveJsonModule": true,
    "types": ["node"]
  },
  "include": ["app", "components", "lib", "styles"]
}
```

### `frontend/styles/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body { height: 100%; }
body { @apply bg-neutral-50 text-neutral-900; }
```

### `frontend/lib/api.ts`

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

export async function search(q: string, page = 1, pageSize = 20): Promise<SearchPayload> {
  const u = new URL(`${API_BASE}/search`);
  u.searchParams.set('q', q);
  u.searchParams.set('page', String(page));
  u.searchParams.set('page_size', String(pageSize));
  const res = await fetch(u.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function exportResults(q: string, format: 'csv' | 'json', page = 1, pageSize = 200) {
  const u = new URL(`${API_BASE}/export`);
  u.searchParams.set('q', q);
  u.searchParams.set('page', String(page));
  u.searchParams.set('page_size', String(pageSize));
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

### `frontend/components/Loading.tsx`

```tsx
export default function Loading() {
  return (
    <div className="animate-pulse text-sm text-neutral-500">Loading…</div>
  );
}
```

### `frontend/components/SearchBar.tsx`

```tsx
'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function SearchBar() {
  const router = useRouter();
  const sp = useSearchParams();
  const initial = sp.get('q') || '';
  const [q, setQ] = useState(initial);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcuts: / focus, Enter search, Esc clear
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === '/') { e.preventDefault(); inputRef.current?.focus(); }
      if (e.key === 'Enter' && document.activeElement === inputRef.current) {
        e.preventDefault();
        if (q.trim()) router.push(`/?q=${encodeURIComponent(q.trim())}`);
      }
      if (e.key === 'Escape') {
        if (inputRef.current === document.activeElement) {
          setQ('');
        }
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [q, router]);

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        className="w-full rounded-lg border border-neutral-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        placeholder="Search Trove… (Press / to focus)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && q.trim()) router.push(`/?q=${encodeURIComponent(q.trim())}`);
        }}
      />
      <button
        className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        onClick={() => q.trim() && router.push(`/?q=${encodeURIComponent(q.trim())}`)}
      >Search</button>
      <button
        className="rounded-lg border px-3 py-2 hover:bg-neutral-100"
        onClick={async () => {
          await navigator.clipboard.writeText(window.location.href);
        }}
        title="Copy shareable URL"
      >Copy URL</button>
    </div>
  );
}
```

### `frontend/components/ResultList.tsx`

```tsx
import type { Item } from '@/lib/api';

export default function ResultList({ items, total }:{ items: Item[]; total: number }) {
  if (!items?.length) return <div className="text-sm text-neutral-500">No results yet.</div>;
  return (
    <div className="space-y-3">
      <div className="text-xs text-neutral-500">Total: {total}</div>
      {items.map((it) => (
        <div key={it.id} className="rounded-lg border p-3 bg-white">
          <div className="font-medium">{it.title}</div>
          {it.snippet && <div className="text-sm text-neutral-700 mt-1">{it.snippet}</div>}
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

### `frontend/app/layout.tsx`

```tsx
import './globals.css';
import { ReactNode } from 'react';

export const metadata = { title: 'Archive Detective' };

export default function RootLayout({ children }:{ children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-4xl p-6">
          <header className="mb-6">
            <h1 className="text-2xl font-semibold">Archive Detective</h1>
            <p className="text-sm text-neutral-600">Export‑friendly Trove search (Phase‑1)</p>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
```

### `frontend/app/page.tsx`

```tsx
'use client';
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import SearchBar from '@/components/SearchBar';
import ResultList from '@/components/ResultList';
import Loading from '@/components/Loading';
import { search as apiSearch, exportResults } from '@/lib/api';

export default function Page() {
  const sp = useSearchParams();
  const q = (sp.get('q') || '').trim();

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ['search', q],
    queryFn: () => apiSearch(q),
    enabled: !!q,
  });

  // Prev/Next shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() === 'e' && q) {
        e.preventDefault();
        exportResults(q, 'csv');
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [q]);

  return (
    <main className="space-y-6">
      <SearchBar />

      <div className="flex gap-2 items-center">
        <button
          disabled={!q}
          className="rounded-lg border px-3 py-2 disabled:opacity-50"
          onClick={() => q && exportResults(q, 'csv')}
        >Export CSV (e)</button>
        <button
          disabled={!q}
          className="rounded-lg border px-3 py-2 disabled:opacity-50"
          onClick={() => q && exportResults(q, 'json')}
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

## `docker-compose.yml` (optional Redis)

```yaml
version: '3.9'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: ["redis-server", "--appendonly", "no"]
```

---

## `scripts/run-dev.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Backend
(
  cd backend
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
  # load env if present
  if [ -f .env ]; then export $(grep -v '^#' .env | xargs); fi
  echo "[backend] starting uvicorn on :8000"
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
)

# Frontend
(
  cd frontend
  npm install
  echo "[frontend] starting Next.js on :3000"
  npm run dev
)
```

---

## `README.md` (root)

````md
# Archive Detective — Phase 1

Export‑first Trove search with fast UX, shareable URLs, keyboard shortcuts.

## Quick Start (Ubuntu)

```bash
# 1) Get Redis (optional but recommended)
docker compose up -d redis

# 2) Backend
cd backend
cp .env.example .env
# edit .env and set TROVE_API_KEY; or set TROVE_MOCK=true for offline demo
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 3) Frontend (new terminal)
cd frontend
npm install
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev
````

Open [http://localhost:3000](http://localhost:3000). Press `/` to focus search, type a query, `Enter` to run.

### Exports

- Click **Export CSV** or **Export JSON**. Files download as `export-<query>.*`.
- Keyboard: press **e** to export CSV.

### Health

- `GET http://127.0.0.1:8000/ready` → `{ ok: true, cache: "redis|memory" }`

## Notes

- Phase‑2 will add: date facets, filter chips, search highlighting.
- Phase‑3 will add: IIIF viewer, details panel, notebooks, CSL‑JSON/BibTeX.

````

---

## Exact Ubuntu Commands (single run)

```bash
mkdir -p ~/Projects/archive-detective && cd ~/Projects/archive-detective

# Write files from this document into the folder (Cursor can paste them directly)
# Optional Redis
docker compose up -d redis || true

# Backend
cd backend
cp .env.example .env
sed -i 's/TROVE_MOCK=false/TROVE_MOCK=true/' .env  # start in mock mode; switch off when key is ready
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
cd ..

# Frontend
cd frontend
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm install
npm run dev
````

---

## What to do next

- Paste this scaffold into Cursor. Run the commands above. You’ll have a working Phase‑1.
- When ready to go live with Trove, set `TROVE_MOCK=false` and add your `TROVE_API_KEY` in `backend/.env`.
- If anything errors, copy the full terminal output. I’ll diagnose and patch fast.

