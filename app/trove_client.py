"""Trove API client with modern async patterns."""

import logging
from typing import Any, Literal

import httpx

from app.exceptions import ConfigurationError, NetworkError, TroveAPIError

logger = logging.getLogger(__name__)


class TroveClient:
    """Async client for Trove API v3."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.trove.nla.gov.au/v3",
        timeout: float = 15.0,
    ):
        if not api_key:
            raise ConfigurationError("Trove API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        """Get request headers with API key."""
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "User-Agent": "TroveFetcher/2.0",
        }

    async def search(
        self,
        q: str = "",
        category: Literal[
            "newspaper",
            "magazine",
            "book",
            "image",
            "research",
            "diary",
            "music",
            "list",
            "people",
            "all",
        ] = "newspaper",
        n: int = 20,
        s: int = 0,
        encoding: str = "json",
        reclevel: str = "brief",
        l_format: str | None = None,
        l_artType: str | None = None,
        l_place: str | None = None,
        sortby: Literal["relevance", "dateAsc", "dateDesc"] | None = None,
    ) -> dict[str, Any]:
        """
        Search Trove API.

        Args:
            q: Query string
            category: Content category
            n: Number of results (1-100)
            s: Start offset (not used for category="all")
            encoding: Response encoding
            reclevel: Record level (brief/full)
            l_format: Format filter
            l_artType: Art type filter
            l_place: Place filter
            sortby: Sort order

        Returns:
            API response as dictionary

        Raises:
            TroveAPIError: On API errors
            NetworkError: On network errors
        """
        # Build parameters - ensure q is not None
        q_value = q if q is not None else ""
        # Note: Empty queries may work for "all" category but not for specific categories

        params: dict[str, Any] = {
            "q": q_value,
            "category": category,
            "encoding": encoding,
            "reclevel": reclevel,
            "n": max(1, min(n, 100)),
        }
        # Trove API: s parameter must NOT be supplied when searching multiple categories
        # Also, only send s if it's > 0 (some categories may not accept s=0)
        if category != "all" and s > 0:
            params["s"] = s
        # Only add filter parameters if they have values
        if l_format and l_format.strip():
            params["l-format"] = l_format.strip()
        if l_artType and l_artType.strip():
            params["l-artType"] = l_artType.strip()
        if l_place and l_place.strip():
            params["l-place"] = l_place.strip()
        if sortby:
            params["sortby"] = sortby

        url = f"{self.base_url}/result"

        # Log request for debugging
        logger.info(f"Trove API request: {url} with params: {params}")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url, params=params)

                # Log response status
                logger.debug(f"Trove API response: {response.status_code}")

                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_text = ""
                try:
                    if e.response:
                        error_text = e.response.text[:1000] if e.response.text else ""
                        # Try to parse JSON error response
                        try:
                            error_json = e.response.json()
                            error_text = str(error_json)[:1000]
                        except (ValueError, TypeError):
                            # JSON parsing failed, use text response
                            pass
                except (AttributeError, httpx.RequestError):
                    # Error accessing response attributes
                    pass

                # Log full error details
                logger.error(
                    f"Trove API error {e.response.status_code if e.response else 'unknown'}: "
                    f"URL={url}, Params={params}, Response={error_text}"
                )

                raise TroveAPIError(
                    status_code=e.response.status_code if e.response else 0,
                    message=f"API returned {e.response.status_code if e.response else 'unknown'}",
                    response_text=error_text,
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Network error connecting to Trove API: {e}")
                raise NetworkError(f"Network error connecting to Trove API: {e}") from e
