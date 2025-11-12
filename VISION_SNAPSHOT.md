# Trove Research Platform — Vision Snapshot (12 Nov 2025, AEST)

## 1) What we're building

An **AI-assisted research workbench for Trove** (newspapers + other collections) that lets you **search, read, pin, summarise, cite, and report**—all in one place. Trove's v3 API gives us the collections, facets and pagination; our app layers in memory, LLM features, reporting, and TTS/reader UX so researchers can move from a query to a publishable brief quickly. ([trove.nla.gov.au][1])

**Why these tech choices hold up**

* **FastAPI + Jinja** for a fast server-rendered core with static assets and templates correctly mounted via `StaticFiles` and Jinja, which is the recommended path. ([FastAPI][2])

* **Pydantic v2 Settings** for environment-driven config (API keys, feature flags) — modern, typed, and easily testable. ([docs.pydantic.dev][3])

* **Web Speech API** in the Reader for "Read Aloud" (no server round-trip, works in modern browsers). ([MDN Web Docs][4])

* **OpenSeadragon** for zoomable Trove scans when IIIF tiles exist (battle-tested deep zoom). ([OpenSeadragon][5])

## 2) What's already implemented (high level)

* **End-to-end app** with Search, Reader, Dashboard, Chat/Desk, Studio and Collections, plus 50+ features and 58+ endpoints across components. 

* **Search UX**: two-pane layout, facets (category/year/place/format), active chips, preview, pinning, TTS, pagination; backed by Trove v3 search + facets.  ([trove.nla.gov.au][1])

* **Reader**: full OCR text, zoomable scan viewer, metadata, citation copy, pin-to-collection, TTS controls, keyboard shortcuts. 

* **Chat & Desk**: Archive-Detective commands (`/search`, `/read`, `/summarize`, `/report-pdf`, etc.), context-aware prompts, quick actions. 

* **Reports/Studio**: multi-article briefs, LLM summaries, PDF export, JSON persistence. 

* **Context Store**: SQLite article memory (pinned, views, first/last seen), WAL, pruning; files and outputs directories for artifacts. 

* **Tunnels & Dev**: ngrok tunnelling; note the multi-session limits on free accounts (watch for ERR_NGROK_108). ([Stack Overflow][6])

> Full component inventory, routes, and metrics are in the uploaded build report. 

## 3) Where we're taking it (near-term roadmap)

**A. "Brief Builder" picker (Kingfisher)**

* **Goal**: Build a **no-typing article chooser** that lists the articles you've already touched (session-aware), with badges for **has_summary / has_cards / has_images**.

* **Backend**: Add `GET /api/brief/articles` returning `[{ trove_id, title, date, source, pinned, last_seen, has_summary, has_cards, has_images }]`. Compute flags from existing tables (don't add columns yet). **Stable:** list is derived from the current context store. 

* **Frontend**: Replace the raw ID box with a searchable list + "Enter ID manually" fallback; reuse our badge styles from Reader/Collections.

**B. Kingfisher card extraction**

* Wire `/kingfisher` to the extractor endpoint for **on-article card generation** (quote/event/person/place/object). Keep JSON-only parsing to avoid prompt-format drift.

* De-risk with: empty-input guard, content-length guard, and "LLM unavailable → extractive fallback".

**C. Reader polish for historians**

* Add **inline cite** button that copies Trove permalink + date + publication; ensure scan/ocr toggle is one click.

* Improve **keyboard nav** (←/→ article, `p` pin, `c` cite, `s` speak).

**D. Collections & Reports**

* One-click "Add to draft" in results/reader → accumulates in `/studio`, always showing **#sources** count and export status.

## 4) Cleanups & risks to burn down

* **Template cache-busting**: keep the `request.url_for(...)` → `str()` cast in the helper to avoid URL object concatenation exceptions in Jinja templates (we hit this). ([FastAPI][2])

* **Config drift**: centralise all flags in Pydantic Settings; validate `TROVE_API_KEY`/`OPENAI_API_KEY` at startup with actionable error messages. ([docs.pydantic.dev][3])

* **ngrok friction**: prefer a **single agent with multiple tunnels via config**, or run a reverse proxy; avoid session-cap errors in demos. ([Stack Overflow][6])

* **IIIF robustness**: detect when Trove lacks tiles and fall back gracefully to stored images/OpenSeadragon placeholder. ([OpenSeadragon][5])

## 5) What to ask Cursor to do next (exact tasks)

1. **Brief API & UI**

   * Add `GET /api/brief/articles` as above.

   * In `/kingfisher`, replace the free-text ID field with a **selectable recent-articles list** (search as you type, badges for summary/cards/images).

2. **Kingfisher endpoints**

   * Ensure `/kingfisher/extract-cards` and `/kingfisher/extract-batch` exist and are called from the page; handle timeouts and empty input with clear UI toasts.

3. **Reader shortcuts & cite**

   * Implement `p/c/s/←/→` bindings and a "Copy citation" service that formats Trove references consistently.

4. **Studio hand-off**

   * Add "Add to draft" buttons across Search/Reader; instrument Studio to always display the draft's item count and export controls.

If you want, I can turn those into a **Cursor planning prompt** and a **PR checklist** in your repo's `/docs/` so it's traceable.

---

Thanks for running hard on this—there's a lot already in place. The steps above keep momentum on the **brief-creation flow** (your highest-leverage path), while tightening reliability and demo polish.

[1]: https://trove.nla.gov.au/about/create-something/using-api/v3/api-technical-guide "API technical guide - Trove"
[2]: https://fastapi.tiangolo.com/tutorial/static-files/ "Static Files - FastAPI"
[3]: https://docs.pydantic.dev/latest/concepts/pydantic_settings/ "Settings Management - Pydantic Validation"
[4]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API "Web Speech API - Web APIs | MDN - MDN Web Docs"
[5]: https://openseadragon.github.io/ "OpenSeadragon"
[6]: https://stackoverflow.com/questions/72498913/pyngrok-flask-your-account-is-limited-to-1-simultaneous-ngrok-agent-session "Pyngrok & Flask, Your account is limited to 1 simultaneous ngrok agent ..."

