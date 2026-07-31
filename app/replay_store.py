from __future__ import annotations

import asyncio
from typing import Protocol


class ReplayStore(Protocol):
    async def claim(self, key_id: str, nonce: str, *, now: int) -> bool: ...


class MemoryReplayStore:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._claims: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    async def claim(self, key_id: str, nonce: str, *, now: int) -> bool:
        key = (key_id, nonce)
        async with self._lock:
            cutoff = now - self.ttl_seconds
            self._claims = {
                item: claimed_at
                for item, claimed_at in self._claims.items()
                if claimed_at > cutoff
            }
            if key in self._claims:
                return False
            self._claims[key] = now
            return True


class RedisReplayStore:
    def __init__(self, redis_client: object, ttl_seconds: int = 600) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    async def claim(self, key_id: str, nonce: str, *, now: int) -> bool:
        del now
        key = f"ym30:nonce:{key_id}:{nonce}"
        result = await self.redis.set(
            key, "1", nx=True, ex=self.ttl_seconds  # type: ignore[attr-defined]
        )
        return bool(result)
