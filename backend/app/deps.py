import os
from collections.abc import AsyncGenerator

import httpx

from .caching import Cache


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    timeout = httpx.Timeout(20.0, read=30.0)
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": "ArchiveDetective/1.0"}
    ) as client:
        yield client


_cache: Cache | None = None


async def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(redis_url=os.getenv("REDIS_URL"), ttl_seconds=300)
        await _cache.connect()
    return _cache
