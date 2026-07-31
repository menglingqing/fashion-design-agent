from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any, Protocol


JSONDict = dict[str, Any]


class IdempotencyStore(Protocol):
    async def get(self, execution_id: str) -> JSONDict | None: ...

    async def put(self, execution_id: str, result: JSONDict) -> None: ...


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, JSONDict] = {}
        self._lock = asyncio.Lock()

    async def get(self, execution_id: str) -> JSONDict | None:
        async with self._lock:
            value = self._results.get(execution_id)
            return deepcopy(value) if value is not None else None

    async def put(self, execution_id: str, result: JSONDict) -> None:
        async with self._lock:
            self._results[execution_id] = deepcopy(result)


class RedisIdempotencyStore:
    def __init__(self, redis_client: object, ttl_seconds: int = 86_400) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    async def get(self, execution_id: str) -> JSONDict | None:
        value = await self.redis.get(  # type: ignore[attr-defined]
            f"ym30:result:{execution_id}"
        )
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def put(self, execution_id: str, result: JSONDict) -> None:
        await self.redis.set(  # type: ignore[attr-defined]
            f"ym30:result:{execution_id}",
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            ex=self.ttl_seconds,
        )
