# Archive Detective — Phase 3

Adds **result details panel**, **zoomable viewer**, **notebook (local, W3C‑Annotation export)**, and **per‑item citations (CSL‑JSON/BibTeX)** — all wired to the existing scaffold without breaking changes.

**Scope**
- Details modal/panel opened from any result
- Zoom viewer (OpenSeadragon) for plain images (and IIIF Image API tile sources if present)
- Notebook: save items, add notes & tags, persist to `localStorage`
- Export notebook as **Annotation JSON‑LD**
- Per‑item citation export: **CSL‑JSON** or **BibTeX** via backend

> Minimal churn: one new backend utility + endpoint; frontend gets new components and a `/notebook` route.

---

## Backend Changes

### 1) `backend/app/utils/citation.py` (new)
```python
from typing import Dict, Optional
from datetime import datetime

def _date_parts(d: Optional[str]):
    if not d:
        return None
    try:
        if len(d) == 10:
            dt = datetime.strptime(d, "%Y-%m-%d")
            return [[dt.year, dt.month, dt.day]]
        if len(d) == 7:
            dt = datetime.strptime(d, "%Y-%m")
            return [[dt.year, dt.month]]
        if len(d) == 4 and d.isdigit():
            return [[int(d)]]
    except Exception:
        return None
    return None

def _ctype(t: str) -> str:
    tl = (t or "").lower()
    if "book" in tl:
        return "book"
    if "article" in tl or "news" in tl or "newspaper" in tl:
        return "article-newspaper"
    if "picture" in tl or "photo" in tl or "image" in tl or "graphic" in tl:
        return "graphic"
    return "document"

def item_to_csl_json(item: Dict) -> Dict:
    ctype = _ctype(item.get("type") or "")
    issued = _date_parts(item.get("date"))
    data = {
        "type": ctype,
        "id": item.get("id"),
        "title": item.get("title"),
        "URL": item.get("url"),
        "source": item.get("source") or "Trove",
    }
    if issued:
        data["issued"] = {"date-parts": issued}
    return data

def item_to_bibtex(item: Dict) -> str:
    key = (item.get("id") or "item").replace("/", "_").replace(" ", "_")
    title = (item.get("title") or "").replace("{", "\\{").replace("}", "\\}")
    url = item.get("url") or ""
    d = item.get("date") or ""
    year = d[:4] if len(d) >= 4 and d[:4].isdigit() else ""
    tl = (item.get("type") or "").lower()
    entry_type = "book" if "book" in tl else ("article" if ("article" in tl or "news" in tl) else "misc")
    bib = f"@{entry_type}{{{key},\n  title = {{{title}}},\n"
    if year:
        bib += f"  year = {{{year}}},\n"
    if url:
        bib += f"  url = {{{url}}},\n"
    bib += f"  note = {{Source: {item.get('source') or 'Trove'}}}\n}}\n"
    return bib
```

### 2) `backend/app/main.py` — add citation endpoint
Append **below** existing routes:
```python
from fastapi import Body
from .utils.citation import item_to_csl_json, item_to_bibtex

@app.post("/citation")
async def citation(
    item: NormalizedItem = Body(...),
    format: str = Query("csljson", pattern="^(csljson|bibtex)$"),
):
    data = item.model_dump()
    if format == "csljson":
        payload = orjson.dumps(item_to_csl_json(data))
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=citation-{item.id}.json"},
        )
    text = item_to_bibtex(data).encode("utf-8")
    return StreamingResponse(
        iter([text]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=citation-{item.id}.bib"},
    )
```

> No dependency changes for backend.

---

## Frontend Changes

### 0) Install viewer dependency
```bash
cd ~/Projects/archive-detective/frontend
npm install openseadragon
```

### 1) `frontend/lib/citation.ts` (new)
```ts
import { API_BASE, Item } from './api';

export async function exportCitation(item: Item, format: 'csljson'|'bibtex') {
  const u = new URL(`${API_BASE}/citation`);
  u.searchParams.set('format', format);
  const res = await fetch(u.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  });
  if (!res.ok) throw new Error(`Citation export failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `citation-${(item.id || 'item')}.${format === 'bibtex' ? 'bib' : 'json'}`;
  a.click();
}
```

### 2) `frontend/lib/notebook.ts` (new)
```ts
import type { Item } from './api';

export type NotebookEntry = { item: Item; note?: string; tags?: string[] };
const KEY = 'ad.notebook.v1';

function load(): NotebookEntry[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}
function save(entries: NotebookEntry[]) {
  localStorage.setItem(KEY, JSON.stringify(entries));
}

export function getNotebook(): NotebookEntry[] { return load(); }
export function addToNotebook(entry: NotebookEntry) {
  const cur = load();
  if (!cur.find(e => e.item.id === entry.item.id)) {
    cur.push(entry); save(cur);
  }
}
export function removeFromNotebook(id: string) {
  save(load().filter(e => e.item.id !== id));
}
export function upsertNotebookEntry(entry: NotebookEntry) {
  const cur = load();
  const i = cur.findIndex(e => e.item.id === entry.item.id);
  if (i >= 0) cur[i] = entry; else cur.push(entry);
  save(cur);
}
export function exportNotebookJSONLD(entries: NotebookEntry[]) {
  const ctx = 'http://www.w3.org/ns/anno.jsonld';
  const anns = entries.map(e => ({
    '@context': ctx,
    'type': 'Annotation',
    'motivation': 'commenting',
    'body': [
      ...(e.note ? [{ type: 'TextualBody', value: e.note, purpose: 'commenting', format: 'text/plain' }] : []),
      ...((e.tags || []).map(t => ({ type: 'TextualBody', purpose: 'tagging', value: t })))
    ],
    'target': e.item.url || e.item.id,
  }));
  const blob = new Blob([JSON.stringify(anns, null, 2)], { type: 'application/ld+json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'notebook-annotations.jsonld';
  a.click();
}
```

### 3) `frontend/components/ZoomViewer.tsx` (new)
```tsx
'use client';
import { useEffect, useRef } from 'react';

export default function ZoomViewer({ imageUrl }: { imageUrl?: string }) {
  const elRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!imageUrl || !elRef.current) return;
    let viewer: any; let cancelled = false;
    (async () => {
      const OSD = (await import('openseadragon')).default;
      if (cancelled) return;
      viewer = OSD({
        element: elRef.current!,
        showNavigationControl: true,
        preserveViewport: true,
        tileSources: { type: 'image', url: imageUrl },
      });
    })();
    return () => { cancelled = true; try { viewer && viewer.destroy(); } catch {} };
  }, [imageUrl]);

  if (!imageUrl) return <div className="text-sm text-neutral-500">No preview available</div>;
  return <div ref={elRef} className="w-full h-96 rounded border overflow-hidden" />;
}
```

### 4) `frontend/components/DetailsModal.tsx` (new)
```tsx
'use client';
import { useEffect, useState } from 'react';
import type { Item } from '@/lib/api';
import ZoomViewer from '@/components/ZoomViewer';
import { addToNotebook, upsertNotebookEntry } from '@/lib/notebook';
import { exportCitation } from '@/lib/citation';

export default function DetailsModal({ item, onClose }:{ item: Item; onClose: ()=>void }) {
  const [note, setNote] = useState('');
  const [tags, setTags] = useState('');

  function save() {
    const t = tags.split(',').map(s => s.trim()).filter(Boolean);
    upsertNotebookEntry({ item, note, tags: t });
    onClose();
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent){ if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-6">
      <div className="w-full max-w-4xl rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b p-4">
          <div className="font-semibold">Details</div>
          <button className="text-xl" onClick={onClose}>×</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
          <div>
            <div className="text-lg font-medium mb-2">{item.title}</div>
            <div className="text-sm text-neutral-600 mb-2">{item.date} {item.type ? `· ${item.type}` : ''} · {item.source}</div>
            <div className="mb-3 text-sm text-neutral-800">{item.snippet}</div>
            <div className="flex gap-2 mb-4">
              {item.url && <a className="rounded border px-3 py-2" href={item.url} target="_blank">Open source</a>}
              <button className="rounded border px-3 py-2" onClick={() => exportCitation(item, 'csljson')}>Export CSL‑JSON</button>
              <button className="rounded border px-3 py-2" onClick={() => exportCitation(item, 'bibtex')}>Export BibTeX</button>
            </div>
            <div className="space-y-2">
              <label className="block text-xs text-neutral-600">Notes</label>
              <textarea className="w-full rounded border p-2" rows={4} value={note} onChange={e=>setNote(e.target.value)} placeholder="Your notes…" />
              <label className="block text-xs text-neutral-600">Tags (comma‑separated)</label>
              <input className="w-full rounded border p-2" value={tags} onChange={e=>setTags(e.target.value)} placeholder="harwood, sugar, 1930s" />
              <div className="flex gap-2">
                <button className="rounded bg-blue-600 text-white px-3 py-2" onClick={save}>Save to Notebook</button>
                <button className="rounded border px-3 py-2" onClick={onClose}>Close</button>
              </div>
            </div>
          </div>
          <div>
            <ZoomViewer imageUrl={item.thumbnail} />
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 5) `frontend/components/ResultList.tsx` (replace: add Details/Save buttons)
```tsx
import type { Item } from '@/lib/api';
import { addToNotebook } from '@/lib/notebook';

export default function ResultList({ items, total, onOpen }:{ items: Item[]; total: number; onOpen: (item: Item)=>void }) {
  if (!items?.length) return <div className="text-sm text-neutral-500">No results yet.</div>;
  return (
    <div className="space-y-3">
      <div className="text-xs text-neutral-500">Total: {total}</div>
      {items.map((it) => (
        <div key={it.id} className="rounded-lg border p-3 bg-white">
          <div className="font-medium">{it.title}</div>
          {it.snippet && <div className="text-sm text-neutral-700 mt-1">{it.snippet}</div>}
          <div className="text-xs text-neutral-500 mt-2 flex flex-wrap gap-3 items-center">
            {it.date && <span>{it.date}</span>}
            {it.type && <span>· {it.type}</span>}
            <span>· {it.source}</span>
            {it.url && (<a className="text-blue-700 underline" href={it.url} target="_blank">Open source</a>)}
            <button className="ml-auto rounded border px-3 py-1.5" onClick={() => onOpen(it)}>Details</button>
            <button className="rounded border px-3 py-1.5" onClick={() => addToNotebook({ item: it })}>Save</button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 6) `frontend/app/notebook/page.tsx` (new)
```tsx
'use client';
import { useEffect, useState } from 'react';
import { getNotebook, removeFromNotebook, upsertNotebookEntry, exportNotebookJSONLD, NotebookEntry } from '@/lib/notebook';

export default function NotebookPage() {
  const [entries, setEntries] = useState<NotebookEntry[]>([]);

  useEffect(() => { setEntries(getNotebook()); }, []);

  function update(i: number, patch: Partial<NotebookEntry>) {
    const e = { ...entries[i], ...patch } as NotebookEntry;
    upsertNotebookEntry(e);
    const nxt = [...entries]; nxt[i] = e; setEntries(nxt);
  }

  return (
    <main className="mx-auto max-w-4xl p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Notebook</h1>
      <div className="flex gap-2">
        <button className="rounded border px-3 py-2" onClick={() => exportNotebookJSONLD(entries)}>Export as Annotation JSON‑LD</button>
        <button className="rounded border px-3 py-2" onClick={() => setEntries(getNotebook())}>Refresh</button>
      </div>
      {!entries.length && <div className="text-sm text-neutral-500">No saved items yet.</div>}
      <div className="space-y-4">
        {entries.map((e, i) => (
          <div key={e.item.id} className="rounded border bg-white p-3">
            <div className="font-medium">{e.item.title}</div>
            <div className="text-xs text-neutral-500 mb-2">{e.item.date} {e.item.type ? `· ${e.item.type}` : ''} · {e.item.source}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-neutral-600">Notes</label>
                <textarea className="w-full rounded border p-2" rows={3} value={e.note || ''} onChange={ev => update(i, { note: ev.target.value })} />
              </div>
              <div>
                <label className="block text-xs text-neutral-600">Tags (comma‑separated)</label>
                <input className="w-full rounded border p-2" value={(e.tags || []).join(', ')} onChange={ev => update(i, { tags: ev.target.value.split(',').map(s=>s.trim()).filter(Boolean) })} />
              </div>
            </div>
            <div className="mt-2 flex gap-2">
              {e.item.url && <a className="rounded border px-3 py-2" href={e.item.url} target="_blank">Open source</a>}
              <button className="rounded border px-3 py-2" onClick={() => { removeFromNotebook(e.item.id); setEntries(entries.filter(x => x.item.id !== e.item.id)); }}>Remove</button>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
```

### 7) `frontend/app/page.tsx` (replace: wire modal)
```tsx
'use client';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import SearchBar from '@/components/SearchBar';
import ResultList from '@/components/ResultList';
import Loading from '@/components/Loading';
import DetailsModal from '@/components/DetailsModal';
import { search as apiSearch, exportResults } from '@/lib/api';
import type { Item } from '@/lib/api';

export default function Page() {
  const sp = useSearchParams();
  const q = (sp.get('q') || '').trim();
  const [selected, setSelected] = useState<Item | null>(null);

  const { data, isFetching, error } = useQuery({
    queryKey: ['search', q],
    queryFn: () => apiSearch(q),
    enabled: !!q,
  });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() === 'e' && q) { e.preventDefault(); exportResults(q, 'csv'); }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [q]);

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <SearchBar />
        <a className="ml-3 rounded border px-3 py-2" href="/notebook">Notebook</a>
      </div>

      <div className="flex gap-2 items-center">
        <button disabled={!q} className="rounded-lg border px-3 py-2 disabled:opacity-50" onClick={() => q && exportResults(q, 'csv')}>Export CSV (e)</button>
        <button disabled={!q} className="rounded-lg border px-3 py-2 disabled:opacity-50" onClick={() => q && exportResults(q, 'json')}>Export JSON</button>
        {isFetching && <Loading />}
      </div>

      {error && <div className="text-red-700">{String((error as Error).message)}</div>}

      <ResultList items={data?.items || []} total={data?.total || 0} onOpen={(it) => setSelected(it)} />

      {selected && <DetailsModal item={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}
```

> No changes needed to `layout.tsx` or Tailwind config.

---

## Commands (Ubuntu)
```bash
# Backend: add citation utility & endpoint
cd ~/Projects/archive-detective/backend
# create app/utils/citation.py from above, then edit app/main.py to append the /citation route
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend: install viewer and add new files
cd ../frontend
npm install openseadragon
# add the new files and replace the listed ones
npm run dev
```

## Quick Test
1) Search something; click **Details** on any result → modal opens.
2) If the item has a `thumbnail` (or any plain image URL), the zoom viewer activates; else you’ll see a placeholder.
3) Add a note and tags → **Save to Notebook**.
4) Click **Notebook** (top right) → entries list with editable notes/tags.
5) **Export as Annotation JSON‑LD** → downloads `notebook-annotations.jsonld`.
6) In Details, try **Export CSL‑JSON** and **Export BibTeX** for the selected item.

If anything errors, paste the full backend traceback and the browser console. I’ll patch with minimal churn.

