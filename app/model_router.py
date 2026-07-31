from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from app.config import Settings


class RetryableModelError(Exception):
    pass


class NonRetryableModelError(Exception):
    pass


class AllModelsUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("All configured model providers are temporarily unavailable")


@dataclass(frozen=True)
class ModelReply:
    content: str
    provider: str
    model: str


class ChatClient(Protocol):
    async def complete(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply: ...


class OpenAIChatClient:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        include_user_id: bool = False,
    ) -> None:
        if not api_key or not model:
            raise NonRetryableModelError("configuration")
        self.provider = provider
        self.model = model
        self.include_user_id = include_user_id
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def complete(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        extra_body = {"user_id": user_id} if self.include_user_id else None
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                stream=False,
                extra_body=extra_body,
            )
        except (OpenAIAuthenticationError, PermissionDeniedError) as exc:
            raise NonRetryableModelError("authentication") from exc
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            raise RetryableModelError("temporary") from exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                raise RetryableModelError("temporary") from exc
            raise NonRetryableModelError("provider_request") from exc

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise RetryableModelError("empty_response")
        return ModelReply(
            content=content,
            provider=self.provider,
            model=self.model,
        )


class ModelRouter:
    def __init__(self, primary: ChatClient, fallback: ChatClient | None) -> None:
        self.primary = primary
        self.fallback = fallback

    async def generate(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        try:
            primary_reply = await self.primary.complete(messages, user_id)
            if not primary_reply.content.strip():
                raise RetryableModelError("empty_response")
            return primary_reply
        except NonRetryableModelError:
            raise
        except RetryableModelError:
            if self.fallback is None:
                raise AllModelsUnavailable() from None

        try:
            fallback_reply = await self.fallback.complete(messages, user_id)
            if not fallback_reply.content.strip():
                raise RetryableModelError("empty_response")
            return fallback_reply
        except (RetryableModelError, NonRetryableModelError):
            raise AllModelsUnavailable() from None

    async def repair(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        provider: str,
    ) -> ModelReply:
        if provider == "doubao":
            client = self.primary
        elif provider == "deepseek" and self.fallback is not None:
            client = self.fallback
        else:
            raise AllModelsUnavailable()
        try:
            reply = await client.complete(messages, user_id)
        except RetryableModelError:
            raise AllModelsUnavailable() from None
        if not reply.content.strip():
            raise AllModelsUnavailable()
        return reply

    async def generate_fallback(
        self, messages: list[dict[str, str]], user_id: str
    ) -> ModelReply:
        if self.fallback is None:
            raise AllModelsUnavailable()
        try:
            reply = await self.fallback.complete(messages, user_id)
        except (RetryableModelError, NonRetryableModelError):
            raise AllModelsUnavailable() from None
        if not reply.content.strip():
            raise AllModelsUnavailable()
        return reply


def build_model_router(settings: Settings) -> ModelRouter:
    primary = OpenAIChatClient(
        provider="doubao",
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_base_url,
        model=settings.doubao_model,
        timeout_seconds=settings.request_timeout_seconds,
    )
    fallback: OpenAIChatClient | None = None
    if settings.deepseek_api_key:
        fallback = OpenAIChatClient(
            provider="deepseek",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.request_timeout_seconds,
            include_user_id=True,
        )
    return ModelRouter(primary, fallback)
