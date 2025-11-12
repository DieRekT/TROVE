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
        reclevel: str = "brief",  # Changed from "full" to avoid 400 errors
        include: str = "",  # Simplified - can add back if needed
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        offset: Optional[int] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search Trove with optional state filtering."""
        params = {
            "q": q,
            "n": n,
            "category": category,
            "encoding": "json",
        }
        # Only add optional parameters if they have values
        if reclevel:
            params["reclevel"] = reclevel
        if include:
            params["include"] = include
        # Trove API v3 uses token-based pagination (nextStart token), not numeric offsets
        # If offset is a string, it's a token; if it's a number > 0, we'll try it (legacy support)
        if offset is not None:
            if isinstance(offset, str):
                params["s"] = offset  # Token-based pagination
            elif offset > 0:
                params["s"] = int(offset)  # Legacy numeric offset (may not work)
        # Trove API v3 uses l-decade format (e.g., "190" for 1900s, "191" for 1910s)
        # If year range spans multiple decades, we can't filter precisely
        # For now, use decade filter if range fits in one decade, otherwise skip year filter
        if year_from and year_to:
            # Calculate decades
            decade_from = year_from // 10
            decade_to = year_to // 10
            # If range fits in one decade, use it
            if decade_from == decade_to:
                params["l-decade"] = str(decade_from)
            # Otherwise, try to use the starting decade (better than nothing)
            elif decade_to - decade_from <= 2:
                # Use the middle decade if range is small
                mid_decade = (decade_from + decade_to) // 2
                params["l-decade"] = str(mid_decade)
            # For larger ranges, skip year filter (too imprecise with decade format)
        elif year_from:
            params["l-decade"] = str(year_from // 10)
        elif year_to:
            params["l-decade"] = str(year_to // 10)
        # Try state filter - Trove API v3 may support it
        if state:
            # Try the state filter, but don't fail if it's not supported
            try:
                params["l-state"] = state  # "New South Wales" or "Western Australia"
            except Exception:
                pass  # If state filtering causes issues, continue without it

        headers = {"X-API-KEY": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            r = await client.get(TROVE_API, params=params)
            r.raise_for_status()
            return r.json()

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

