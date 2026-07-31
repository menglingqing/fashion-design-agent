from __future__ import annotations

from dataclasses import dataclass
import hashlib

from app.capability_router import route_capability
from app.model_router import AllModelsUnavailable, ModelRouter
from app.output_validation import OutputValidationError, parse_and_validate_output
from app.prompt_loader import load_expert_prompt
from app.schemas import CapabilityInput, ExpertOutput


@dataclass(frozen=True)
class AgentIdentity:
    tenant_id: str
    employee_id: str

    def anonymous_user_id(self) -> str:
        digest = hashlib.sha256(
            f"{self.tenant_id}:{self.employee_id}".encode("utf-8")
        ).hexdigest()
        return f"ym30-{digest[:32]}"


class FashionDesignAgent:
    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router

    async def run(
        self,
        capability_id: str,
        payload: dict[str, object],
        identity: AgentIdentity,
    ) -> ExpertOutput:
        capability_input = CapabilityInput.model_validate(payload)
        route = route_capability(capability_id)
        system_prompt = load_expert_prompt(route)
        user_content = capability_input.model_dump_json()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        user_id = identity.anonymous_user_id()
        reply = await self.model_router.generate(messages, user_id)
        try:
            return parse_and_validate_output(reply.content, route)
        except OutputValidationError:
            repair_messages = [
                *messages,
                {"role": "assistant", "content": reply.content},
                {
                    "role": "user",
                    "content": (
                        "上一条响应未通过 JSON schema 或专业质量门禁。"
                        "请依据系统输出契约重新输出一个完整 JSON object，"
                        "不要添加 JSON 外文字，也不要编造缺失事实。"
                    ),
                },
            ]

        try:
            repaired = await self.model_router.repair(
                repair_messages, user_id, reply.provider
            )
            return parse_and_validate_output(repaired.content, route)
        except (OutputValidationError, AllModelsUnavailable):
            if reply.provider == "deepseek":
                raise

        fallback = await self.model_router.generate_fallback(
            repair_messages, user_id
        )
        return parse_and_validate_output(fallback.content, route)
