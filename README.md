# Trove Fetcher (v3)

- FastAPI app for searching Trove v3 across categories with optional images.
- API key is read from .env (TROVE_API_KEY).
- Uses header `X-API-KEY` (recommended approach).

## Run
bash setup.sh
cp .env.example .env  # add your key
bash run.sh
open http://127.0.0.1:8000

## Usage
- Choose category: newspaper, magazine, book, image, list, etc.
- Optional facets:
  - l_format (works): e.g., "Photograph", "Map", "Thesis"
  - l_artType (image category): e.g., "Pictures and photos", "Maps"
  - l_place: e.g., "Australia/New South Wales", "Antarctica"
- Toggle "Show Images" to display thumbnails when available.

## Notes
- v3 search endpoint: /v3/result (with q, category, n, s, reclevel, facets).
- Pagination via n (page size), s (offset).
- Thumbnails derived from:
  - identifier entries with linktype=thumbnail/viewcopy/fulltext
  - or /image?hei=... on trovePageUrl for newspapers (best-effort).
- Respect Trove terms of use for metadata and digitised content.
