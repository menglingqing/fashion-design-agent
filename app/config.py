from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    ym30_key_id: str
    ym30_secret: str = field(repr=False)
    doubao_api_key: str = field(repr=False)
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = ""
    deepseek_api_key: str = field(default="", repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    redis_url: str = field(default="", repr=False)
    nonce_ttl_seconds: int = 600
    request_timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = environ if env is None else env
        return cls(
            ym30_key_id=source.get("YM30_PROVIDER_KEY_ID", ""),
            ym30_secret=source.get("YM30_PROVIDER_SECRET", ""),
            doubao_api_key=source.get("DOUBAO_API_KEY", ""),
            doubao_base_url=source.get(
                "DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
            ),
            doubao_model=source.get("DOUBAO_MODEL", ""),
            deepseek_api_key=source.get("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=source.get(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ),
            deepseek_model=source.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            redis_url=source.get("REDIS_URL", ""),
        )

    def validate_runtime(self) -> None:
        required = {
            "YM30_PROVIDER_KEY_ID": self.ym30_key_id,
            "YM30_PROVIDER_SECRET": self.ym30_secret,
            "DOUBAO_API_KEY": self.doubao_api_key,
            "DOUBAO_MODEL": self.doubao_model,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Missing required configuration: " + ", ".join(missing))
