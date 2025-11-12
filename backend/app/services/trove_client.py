from __future__ import annotations
import os
import httpx
import re
from typing import Dict, Any, List, Optional


TROVE_API = "https://api.trove.nla.gov.au/v3/result"


class TroveClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 25.0):
        self.api_key = api_key or os.getenv("TROVE_API_KEY")
        if not self.api_key:
            raise RuntimeError("TROVE_API_KEY not set")
        self.timeout = timeout

    async def search(
        self,
        q: str,
        n: int = 20,
        category: str = "newspaper",
        reclevel: str = "full",
        include: str = "articleText,links",
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        state: Optional[str] = None,
        offset: Optional[int | str] = None,
    ) -> Dict[str, Any]:
        """Search Trove with optional state filtering."""
        params = {
            "q": q,
            "n": n,
            "category": category,
            "reclevel": reclevel,
            "encoding": "json",
            "include": include,
        }
        # Trove API v3 uses token-based pagination (s parameter can be token or int)
        if offset is not None:
            params["s"] = offset
        # Trove API v3 uses l-year format: "1945-1980", "1945-", or "-1980"
        if year_from and year_to:
            params["l-year"] = f"{year_from}-{year_to}"
        elif year_from:
            params["l-year"] = f"{year_from}-"
        elif year_to:
            params["l-year"] = f"-{year_to}"
        # State filter - Trove API v3 may not support l-state parameter
        # Try to use it, but don't fail if it's not supported
        # Note: State filtering may need to be done post-fetch
        if state:
            state_map = {
                "NSW": "New South Wales",
                "WA": "Western Australia",
                "VIC": "Victoria",
                "QLD": "Queensland",
                "SA": "South Australia",
                "TAS": "Tasmania",
                "NT": "Northern Territory",
                "ACT": "Australian Capital Territory",
            }
            full_state = state_map.get(state.upper(), state)
            # Try adding state filter, but API may not support it
            # If API returns 400, we'll handle it in the calling code
            params["l-state"] = full_state

        headers = {"X-API-KEY": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                r = await client.get(TROVE_API, params=params)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                # If 400 error and state parameter was used, try without it
                if e.response.status_code == 400 and state and "l-state" in params:
                    # Retry without state filter
                    params_no_state = {k: v for k, v in params.items() if k != "l-state"}
                    r = await client.get(TROVE_API, params=params_no_state)
                    r.raise_for_status()
                    return r.json()
                raise

    @staticmethod
    def extract_hits(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        for cat in payload.get("category", []):
            recs = cat.get("records", {})
            for key in ("article", "work"):
                for rec in recs.get(key, []) or []:
                    hits.append(rec)
        return hits

    @staticmethod
    def article_url(rec: Dict[str, Any]) -> Optional[str]:
        for lnk in rec.get("link", []) or []:
            if lnk.get("linktype") == "resolver":
                return lnk.get("url")
        return rec.get("troveUrl") or rec.get("url")

    @staticmethod
    def year_from_any(rec: Dict[str, Any]) -> Optional[int]:
        for k in ("date", "issued", "year", "publicationDate"):
            v = rec.get(k)
            if not v:
                continue
            m = re.search(r"\b(1[6-9]\d{2}|20\d{2})\b", str(v))
            if m:
                return int(m.group(1))
        return None

