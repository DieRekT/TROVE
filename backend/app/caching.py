import asyncio
import time
from typing import Any

try:
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore


class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
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
    def __init__(self, redis_url: str | None, ttl_seconds: int = 300):
        self.redis_url = redis_url
        self.ttl = ttl_seconds
        self.redis = None
        self.memory = SimpleTTLCache(ttl_seconds)

    async def connect(self):
        if self.redis_url and aioredis:
            try:
                self.redis = aioredis.from_url(
                    self.redis_url, encoding="utf-8", decode_responses=True
                )
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
