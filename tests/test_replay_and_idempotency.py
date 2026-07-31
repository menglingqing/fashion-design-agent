import json

import pytest

from app.idempotency import MemoryIdempotencyStore, RedisIdempotencyStore
from app.config import Settings
from app.main import build_runtime_stores
from app.replay_store import MemoryReplayStore, RedisReplayStore


@pytest.mark.asyncio
async def test_memory_replay_store_claims_once_until_expiry() -> None:
    store = MemoryReplayStore(ttl_seconds=600)
    assert await store.claim("cp_test", "nonce", now=1000) is True
    assert await store.claim("cp_test", "nonce", now=1001) is False
    assert await store.claim("cp_test", "nonce", now=1601) is True


@pytest.mark.asyncio
async def test_memory_idempotency_store_returns_an_isolated_copy() -> None:
    store = MemoryIdempotencyStore()
    result = {"status": "success", "output": {"summary": "original"}}
    await store.put("exec-1", result)
    first = await store.get("exec-1")
    assert first is not None
    first["output"]["summary"] = "changed"
    second = await store.get("exec-1")
    assert second == result


class FakeRedis:
    def __init__(self) -> None:
        self.set_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.values: dict[str, str] = {}

    async def set(self, *args: object, **kwargs: object) -> bool:
        self.set_calls.append((args, kwargs))
        key, value = str(args[0]), str(args[1])
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


@pytest.mark.asyncio
async def test_redis_replay_store_uses_atomic_set_nx_ex() -> None:
    redis = FakeRedis()
    store = RedisReplayStore(redis, ttl_seconds=600)
    assert await store.claim("cp_test", "nonce", now=1000) is True
    _, kwargs = redis.set_calls[0]
    assert kwargs == {"nx": True, "ex": 600}


@pytest.mark.asyncio
async def test_redis_idempotency_store_round_trips_json() -> None:
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=86_400)
    value = {"status": "success", "output": {"summary": "ok"}}
    await store.put("exec-1", value)
    assert json.loads(redis.values["ym30:result:exec-1"]) == value
    assert await store.get("exec-1") == value


def test_runtime_uses_redis_stores_when_redis_url_is_configured() -> None:
    redis = FakeRedis()
    settings = Settings(
        ym30_key_id="cp_test",
        ym30_secret="secret",
        doubao_api_key="key",
        doubao_model="ep-test",
        redis_url="redis://redis:6379/0",
    )
    replay, idempotency = build_runtime_stores(
        settings, redis_factory=lambda url: redis
    )
    assert isinstance(replay, RedisReplayStore)
    assert isinstance(idempotency, RedisIdempotencyStore)
