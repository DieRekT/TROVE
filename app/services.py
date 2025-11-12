"""Business logic services for Trove operations."""

import re
from typing import Any

from app.models import TroveRecord
from app.trove_client import TroveClient
# Import safe_get from utils.py file (not utils package)
import importlib.util
import os
spec = importlib.util.spec_from_file_location("app_utils", os.path.join(os.path.dirname(__file__), "utils.py"))
app_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_utils)
safe_get = app_utils.safe_get


class TroveRecordNormalizer:
    """Service for normalizing Trove API records."""

    @staticmethod
    def extract_image_links(record: dict[str, Any]) -> tuple[str | None, str | None]:
        """
        Extract thumbnail and full image URLs from record identifiers.

        Returns:
            Tuple of (thumbnail_url, full_url)
        """
        thumb = None
        full = None

        identifiers = record.get("identifier") or []
        if isinstance(identifiers, dict):
            identifiers = [identifiers]

        for ident in identifiers:
            if not isinstance(ident, dict):
                continue

            linktype = ident.get("linktype") or ident.get("@linktype")
            value = ident.get("value") or ident.get("#text") or ident.get("id") or None

            if not value:
                continue

            if linktype == "thumbnail" and not thumb:
                thumb = value
            elif linktype in ("viewcopy", "fulltext") and not full:
                full = value

        return thumb, full

    @staticmethod
    def extract_page_image_urls(trove_page_url: str | None) -> tuple[str | None, str | None]:
        """
        Generate image URLs from Trove page URL.

        Returns:
            Tuple of (small_image_url, large_image_url)
        """
        if not trove_page_url:
            return None, None
        # Expect URLs like https://nla.gov.au/nla.news-page16272168
        match = re.search(r"(nla\.news-page\d+)", trove_page_url)
        if match:
            page_id = match.group(1)
            thumb_url = f"/api/trove/page-thumbnail/{page_id}?size=thumb"
            large_url = f"/api/trove/page-thumbnail/{page_id}?size=large"
            return thumb_url, large_url

        # Fallback to legacy pattern (may return HTML shell rather than image)
        small = f"{trove_page_url}/image?hei=180"
        large = f"{trove_page_url}/image?hei=700"
        return small, large

    @staticmethod
    def _normalize_to_string(value: Any) -> str | None:
        """Convert value to string, handling lists and None."""
        if value is None:
            return None
        if isinstance(value, list):
            # Join list items with commas
            return ", ".join(str(item) for item in value if item)
        return str(value) if value else None

    @classmethod
    def normalize_record(cls, record: dict[str, Any], category_code: str) -> TroveRecord:
        """Normalize a Trove API record to a standard format."""
        trove_url = record.get("troveUrl") or record.get("trovePageUrl")

        # Extract ID from URL or record
        item_id = None
        if record.get("id"):
            item_id = str(record.get("id"))
        elif trove_url:
            # Extract numeric ID from Trove URL (e.g., /newspaper/article/12345678)
            match = re.search(r"/(\d{6,})", trove_url)
            if match:
                item_id = match.group(1)

        norm_data: dict[str, Any] = {
            "category": category_code,
            "id": item_id,
            "title": None,
            "subtitle": None,
            "issued": None,
            "publisher_or_source": None,
            "trove_url": trove_url,
            "snippet": cls._normalize_to_string(record.get("snippet")),
            "image_thumb": None,
            "image_full": None,
        }

        if category_code == "newspaper":
            norm_data["title"] = cls._normalize_to_string(
                record.get("heading") or record.get("title")
            )
            norm_data["issued"] = cls._normalize_to_string(record.get("date"))
            source_title = safe_get(record, "title", "title") or safe_get(record, "title") or None
            norm_data["publisher_or_source"] = cls._normalize_to_string(source_title)

            trove_page_url = record.get("trovePageUrl")
            thumb, full = cls.extract_page_image_urls(trove_page_url)
            norm_data["image_thumb"] = thumb
            norm_data["image_full"] = full
        else:
            norm_data["title"] = cls._normalize_to_string(record.get("title"))
            norm_data["issued"] = cls._normalize_to_string(
                record.get("issued") or record.get("date")
            )
            contributor = record.get("contributor") or safe_get(record, "isPartOf", "title")
            norm_data["publisher_or_source"] = cls._normalize_to_string(contributor)

            thumb, full = cls.extract_image_links(record)
            norm_data["image_thumb"] = thumb
            norm_data["image_full"] = full

            # Fallback to page image URLs if no identifier images
            if not norm_data["image_thumb"] and not norm_data["image_full"]:
                trove_page_url = record.get("trovePageUrl")
                thumb, full = cls.extract_page_image_urls(trove_page_url)
                norm_data["image_thumb"] = thumb
                norm_data["image_full"] = full

        return TroveRecord(**norm_data)


async def refresh_article_images(
    article_id: str,
    request: Any = None,
    force: bool = False,
    allow_generation: bool = False,
) -> dict[str, Any]:
    """
    Stub function for refreshing article images.
    Returns empty images list for now.
    """
    return {"images": [], "count": 0}


class TroveSearchService:
    """Service for searching and processing Trove results."""

    def __init__(self, client: TroveClient):
        self.client = client
        self.normalizer = TroveRecordNormalizer()

    async def search(
        self,
        q: str,
        category: str,
        n: int,
        s: int,
        **kwargs: Any,
    ) -> tuple[list[TroveRecord], int]:
        """
        Search Trove and return normalized records.

        Returns:
            Tuple of (normalized_records, total_count)
        """
        # Use full records for newspapers so we can derive page imagery metadata
        reclevel = "full" if category == "newspaper" else "brief"

        data = await self.client.search(
            q=q,
            category=category,
            n=n,
            s=s,
            reclevel=reclevel,
            **kwargs,
        )

        buckets = self._extract_category_buckets(data)
        normalized: list[TroveRecord] = []
        total = 0

        for cat in buckets:
            code = cat.get("code") or cat.get("name") or category
            records_dict = cat.get("records", {})

            if isinstance(records_dict, dict):
                total += int(records_dict.get("total", 0))
                records = self._extract_records_from_dict(records_dict)
            elif isinstance(records_dict, list):
                records = records_dict
            else:
                records = []

            for record in records:
                normalized.append(self.normalizer.normalize_record(record, code))

        return normalized, total

    @staticmethod
    def _extract_category_buckets(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract category buckets from API response."""
        cats = data.get("category") or []
        if isinstance(cats, dict):
            cats = [cats]
        return cats

    @staticmethod
    def _extract_records_from_dict(records_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract record list from records dictionary."""
        records = []
        for container in ("work", "article", "item", "record"):
            val = records_dict.get(container)
            if val:
                if isinstance(val, dict):
                    records.append(val)
                elif isinstance(val, list):
                    records.extend(val)
        return records
