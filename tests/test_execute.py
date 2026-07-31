import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.idempotency import MemoryIdempotencyStore
from app.main import create_app
from app.replay_store import MemoryReplayStore
from app.schemas import ExpertOutput


NOW = 1_785_460_000


def settings() -> Settings:
    return Settings(
        ym30_key_id="cp_test",
        ym30_secret="unit-test-secret",
        doubao_api_key="unused",
        doubao_model="ep-test",
    )


def envelope(
    *,
    execution_id: str = "exec-1",
    capability_id: str = "develop_apparel_style",
    input_value: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "protocol_version": "1.1",
        "execution_id": execution_id,
        "trace_id": "trace-1",
        "capability_id": capability_id,
        "tenant_id": "tenant-1",
        "employee_id": "employee-1",
        "execution_mode": "sync",
        "input": input_value if input_value is not None else {"request": "设计通勤夹克"},
        "conversation_context": {},
        "data_api": {},
        "issued_at": NOW,
        "deadline_at": NOW + 30,
    }


def signed_request(
    value: dict[str, object], *, nonce: str = "nonce-1"
) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            "YM30-CP-V1.1",
            "POST",
            "/execute",
            str(NOW),
            nonce,
            "cp_test",
            str(value["execution_id"]),
            str(value["capability_id"]),
            body_hash,
        ]
    )
    signature = "v1=" + hmac.new(
        b"unit-test-secret", canonical.encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-YM30-Protocol-Version": "1.1",
        "X-YM30-Key-Id": "cp_test",
        "X-YM30-Timestamp": str(NOW),
        "X-YM30-Nonce": nonce,
        "X-YM30-Signature": signature,
        "X-YM30-Execution-Id": str(value["execution_id"]),
        "X-YM30-Capability-Id": str(value["capability_id"]),
        "X-YM30-Body-SHA256": body_hash,
        "Idempotency-Key": str(value["execution_id"]),
    }
    return body, headers


def expert_output() -> ExpertOutput:
    return ExpertOutput.model_validate(
        {
            "summary": "完成",
            "route": "single_style",
            "version": "V0 concept",
            "sections": [{"title": "方案", "content_markdown": "内容"}],
            "decision_log": {
                "confirmed_facts": [],
                "assumptions": [],
                "needs_confirmation": [],
                "changes": [],
            },
            "quality_checks": [
                {"name": "一致性", "status": "pass", "note": "已检查"}
            ],
            "next_action": "确认方向",
        }
    )


class FakeAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self, capability_id: str, payload: dict[str, object], identity: object
    ) -> ExpertOutput:
        self.calls += 1
        return expert_output()


def build_test_app(agent: FakeAgent):
    return create_app(
        settings=settings(),
        replay_store=MemoryReplayStore(),
        idempotency_store=MemoryIdempotencyStore(),
        agent=agent,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_missing_signature_returns_401_without_model_call() -> None:
    agent = FakeAgent()
    async with AsyncClient(
        transport=ASGITransport(app=build_test_app(agent)), base_url="http://test"
    ) as client:
        response = await client.post("/execute", content=b"{}")
    assert response.status_code == 401
    assert agent.calls == 0


@pytest.mark.asyncio
async def test_valid_request_returns_success() -> None:
    agent = FakeAgent()
    body, headers = signed_request(envelope())
    async with AsyncClient(
        transport=ASGITransport(app=build_test_app(agent)), base_url="http://test"
    ) as client:
        response = await client.post("/execute", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["output"]["summary"] == "完成"


@pytest.mark.asyncio
async def test_duplicate_nonce_is_rejected() -> None:
    agent = FakeAgent()
    app = build_test_app(agent)
    body, headers = signed_request(envelope())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.post("/execute", content=body, headers=headers)).status_code == 200
        second = await client.post("/execute", content=body, headers=headers)
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_new_nonce_reuses_idempotent_result_without_model_call() -> None:
    agent = FakeAgent()
    app = build_test_app(agent)
    value = envelope()
    body1, headers1 = signed_request(value, nonce="nonce-1")
    body2, headers2 = signed_request(value, nonce="nonce-2")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/execute", content=body1, headers=headers1)
        second = await client.post("/execute", content=body2, headers=headers2)
    assert first.json() == second.json()
    assert agent.calls == 1


@pytest.mark.asyncio
async def test_missing_business_request_returns_clarification() -> None:
    agent = FakeAgent()
    body, headers = signed_request(envelope(input_value={}))
    async with AsyncClient(
        transport=ASGITransport(app=build_test_app(agent)), base_url="http://test"
    ) as client:
        response = await client.post("/execute", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "clarification_required"
    assert agent.calls == 0
