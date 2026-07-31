import json

import pytest

from app.agent import AgentIdentity, FashionDesignAgent
from app.model_router import ModelReply


def model_output() -> str:
    return json.dumps(
        {
            "summary": "完成单款设计",
            "route": "single_style",
            "version": "V0 concept",
            "sections": [{"title": "方案", "content_markdown": "城市通勤夹克"}],
            "decision_log": {
                "confirmed_facts": [],
                "assumptions": ["默认春秋季"],
                "needs_confirmation": [],
                "changes": [],
            },
            "quality_checks": [
                {"name": "一致性", "status": "pass", "note": "已检查"}
            ],
            "next_action": "确认廓形",
        },
        ensure_ascii=False,
    )


class FakeRouter:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.user_id = ""

    async def generate(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        self.messages = messages
        self.user_id = user_id
        return ModelReply(model_output(), "doubao", "ep-test")


class RepairingRouter:
    def __init__(self, repair_reply: str, fallback_reply: str | None = None) -> None:
        self.repair_reply = repair_reply
        self.fallback_reply = fallback_reply
        self.repair_calls = 0
        self.fallback_calls = 0

    async def generate(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        return ModelReply("not-json", "doubao", "ep-test")

    async def repair(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        provider: str,
    ) -> ModelReply:
        self.repair_calls += 1
        return ModelReply(self.repair_reply, provider, "ep-test")

    async def generate_fallback(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        self.fallback_calls += 1
        assert self.fallback_reply is not None
        return ModelReply(self.fallback_reply, "deepseek", "deepseek-v4-flash")


@pytest.mark.asyncio
async def test_agent_loads_route_and_returns_validated_output() -> None:
    router = FakeRouter()
    agent = FashionDesignAgent(router)
    output = await agent.run(
        "develop_apparel_style",
        {"request": "设计一件城市通勤夹克"},
        AgentIdentity(tenant_id="tenant-private", employee_id="employee-private"),
    )
    assert output.route == "single_style"
    assert router.messages[0]["role"] == "system"
    assert "单款" in router.messages[0]["content"]
    assert router.messages[1]["role"] == "user"
    assert "设计一件城市通勤夹克" in router.messages[1]["content"]
    assert "tenant-private" not in router.user_id
    assert "employee-private" not in router.user_id


@pytest.mark.asyncio
async def test_agent_repairs_invalid_structured_output_once() -> None:
    router = RepairingRouter(repair_reply=model_output())
    agent = FashionDesignAgent(router)  # type: ignore[arg-type]
    output = await agent.run(
        "develop_apparel_style",
        {"request": "设计通勤夹克"},
        AgentIdentity("tenant", "employee"),
    )
    assert output.summary == "完成单款设计"
    assert router.repair_calls == 1
    assert router.fallback_calls == 0


@pytest.mark.asyncio
async def test_agent_falls_back_after_failed_primary_repair() -> None:
    router = RepairingRouter(
        repair_reply="still-not-json", fallback_reply=model_output()
    )
    agent = FashionDesignAgent(router)  # type: ignore[arg-type]
    output = await agent.run(
        "develop_apparel_style",
        {"request": "设计通勤夹克"},
        AgentIdentity("tenant", "employee"),
    )
    assert output.summary == "完成单款设计"
    assert router.repair_calls == 1
    assert router.fallback_calls == 1
