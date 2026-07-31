import pytest

from app.model_router import (
    AllModelsUnavailable,
    ModelReply,
    ModelRouter,
    NonRetryableModelError,
    RetryableModelError,
)


class FakeClient:
    def __init__(
        self, result: ModelReply | Exception, provider: str
    ) -> None:
        self.result = result
        self.provider = provider
        self.calls = 0
        self.user_ids: list[str] = []

    async def complete(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        self.calls += 1
        self.user_ids.append(user_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_primary_success_does_not_call_fallback() -> None:
    primary = FakeClient(ModelReply("{}", "doubao", "ep-test"), "doubao")
    fallback = FakeClient(ModelReply("{}", "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    reply = await router.generate([{"role": "user", "content": "x"}], "user-1")
    assert reply.provider == "doubao"
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_retryable_primary_failure_uses_fallback() -> None:
    primary = FakeClient(RetryableModelError("timeout"), "doubao")
    fallback = FakeClient(ModelReply('{"summary":"ok"}', "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    reply = await router.generate([{"role": "user", "content": "x"}], "user-1")
    assert reply.provider == "deepseek"
    assert fallback.user_ids == ["user-1"]


@pytest.mark.asyncio
async def test_non_retryable_primary_failure_does_not_fallback() -> None:
    primary = FakeClient(NonRetryableModelError("authentication"), "doubao")
    fallback = FakeClient(ModelReply("{}", "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    with pytest.raises(NonRetryableModelError, match="authentication"):
        await router.generate([{"role": "user", "content": "x"}], "user-1")
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_empty_primary_content_is_retryable() -> None:
    primary = FakeClient(ModelReply("  ", "doubao", "ep-test"), "doubao")
    fallback = FakeClient(ModelReply("{}", "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    reply = await router.generate([{"role": "user", "content": "x"}], "user-1")
    assert reply.provider == "deepseek"


@pytest.mark.asyncio
async def test_both_fail_without_leaking_details() -> None:
    primary = FakeClient(RetryableModelError("primary-secret"), "doubao")
    fallback = FakeClient(RetryableModelError("fallback-secret"), "deepseek")
    router = ModelRouter(primary, fallback)
    with pytest.raises(AllModelsUnavailable) as error:
        await router.generate([{"role": "user", "content": "x"}], "user-1")
    rendered = str(error.value)
    assert "primary-secret" not in rendered
    assert "fallback-secret" not in rendered


@pytest.mark.asyncio
async def test_repair_uses_the_named_provider() -> None:
    primary = FakeClient(ModelReply("{}", "doubao", "ep-test"), "doubao")
    fallback = FakeClient(ModelReply("{}", "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    reply = await router.repair(
        [{"role": "user", "content": "repair"}], "user-1", "doubao"
    )
    assert reply.provider == "doubao"
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_explicit_fallback_uses_only_fallback_provider() -> None:
    primary = FakeClient(ModelReply("{}", "doubao", "ep-test"), "doubao")
    fallback = FakeClient(ModelReply("{}", "deepseek", "v4"), "deepseek")
    router = ModelRouter(primary, fallback)
    reply = await router.generate_fallback(
        [{"role": "user", "content": "x"}], "user-1"
    )
    assert reply.provider == "deepseek"
    assert primary.calls == 0
    assert fallback.calls == 1
