from __future__ import annotations

from collections.abc import Callable
import json
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.asyncio import from_url as redis_from_url

from app.agent import AgentIdentity, FashionDesignAgent
from app.config import Settings
from app.idempotency import (
    IdempotencyStore,
    MemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from app.model_router import (
    AllModelsUnavailable,
    NonRetryableModelError,
    build_model_router,
)
from app.output_validation import OutputValidationError
from app.replay_store import MemoryReplayStore, RedisReplayStore, ReplayStore
from app.schemas import ExecutionEnvelope
from app.ym30_auth import AuthenticationError, verify_request


def build_runtime_stores(
    settings: Settings,
    redis_factory: Callable[[str], object] | None = None,
) -> tuple[ReplayStore, IdempotencyStore]:
    if not settings.redis_url:
        return (
            MemoryReplayStore(settings.nonce_ttl_seconds),
            MemoryIdempotencyStore(),
        )
    factory = redis_factory or (
        lambda url: redis_from_url(url, decode_responses=True)
    )
    client = factory(settings.redis_url)
    return (
        RedisReplayStore(client, settings.nonce_ttl_seconds),
        RedisIdempotencyStore(client),
    )


def create_app(
    *,
    settings: Settings | None = None,
    replay_store: ReplayStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    agent: Any | None = None,
    clock: Callable[[], int | float] = time.time,
) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    default_replay, default_idempotency = build_runtime_stores(runtime_settings)
    runtime_replay = replay_store or default_replay
    runtime_idempotency = idempotency_store or default_idempotency
    runtime_agent = agent

    application = FastAPI(title="Fashion Design Expert RCP", version="1.0.0")

    @application.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @application.post("/execute")
    async def execute(request: Request) -> JSONResponse:
        nonlocal runtime_agent
        body = await request.body()
        try:
            verified = verify_request(
                method=request.method,
                path=request.url.path,
                headers=request.headers,
                body=body,
                settings=runtime_settings,
                now=int(clock()),
            )
        except AuthenticationError:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "error": {"code": "unauthorized"}},
            )

        claimed = await runtime_replay.claim(
            verified.key_id, verified.nonce, now=int(clock())
        )
        if not claimed:
            return JSONResponse(
                status_code=401,
                content={"status": "error", "error": {"code": "replay_rejected"}},
            )

        try:
            raw_value = json.loads(body)
            envelope = ExecutionEnvelope.model_validate(raw_value)
        except (json.JSONDecodeError, ValidationError):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": {"code": "invalid_request"}},
            )

        idempotency_key = request.headers.get("Idempotency-Key", "")
        if (
            envelope.execution_id != verified.execution_id
            or envelope.capability_id != verified.capability_id
            or (idempotency_key and idempotency_key != verified.execution_id)
        ):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": {"code": "identity_mismatch"}},
            )

        cached = await runtime_idempotency.get(verified.execution_id)
        if cached is not None:
            return JSONResponse(status_code=200, content=cached)

        request_text = envelope.input.get("request")
        if not isinstance(request_text, str) or not request_text.strip():
            result = {
                "status": "clarification_required",
                "output": {
                    "questions": ["请说明希望服装设计专家完成的具体任务。"]
                },
            }
            await runtime_idempotency.put(verified.execution_id, result)
            return JSONResponse(status_code=200, content=result)

        if runtime_agent is None:
            try:
                runtime_settings.validate_runtime()
                runtime_agent = FashionDesignAgent(
                    build_model_router(runtime_settings)
                )
            except (ValueError, NonRetryableModelError):
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "error": {"code": "provider_not_configured"},
                    },
                )

        try:
            output = await runtime_agent.run(
                envelope.capability_id,
                envelope.input,
                AgentIdentity(
                    tenant_id=envelope.tenant_id,
                    employee_id=envelope.employee_id,
                ),
            )
        except ValidationError:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": {"code": "invalid_input"}},
            )
        except (AllModelsUnavailable, OutputValidationError):
            return JSONResponse(
                status_code=200,
                content={
                    "status": "error",
                    "error": {"code": "generation_unavailable", "retryable": True},
                },
            )
        except NonRetryableModelError:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "error",
                    "error": {"code": "model_configuration_error"},
                },
            )

        result = {
            "status": "success",
            "output": output.model_dump(mode="json"),
        }
        await runtime_idempotency.put(verified.execution_id, result)
        return JSONResponse(status_code=200, content=result)

    return application


app = create_app()
