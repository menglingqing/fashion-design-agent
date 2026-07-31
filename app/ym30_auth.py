from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from collections.abc import Mapping

from app.config import Settings


class AuthenticationError(Exception):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class VerifiedRequest:
    key_id: str
    timestamp: int
    nonce: str
    execution_id: str
    capability_id: str


def _header(headers: Mapping[str, str], name: str) -> str:
    lower_name = name.lower()
    return next(
        (str(value) for key, value in headers.items() if key.lower() == lower_name),
        "",
    )


def verify_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    settings: Settings,
    now: int,
) -> VerifiedRequest:
    protocol = _header(headers, "X-YM30-Protocol-Version")
    key_id = _header(headers, "X-YM30-Key-Id")
    timestamp_text = _header(headers, "X-YM30-Timestamp")
    nonce = _header(headers, "X-YM30-Nonce")
    signature = _header(headers, "X-YM30-Signature")
    execution_id = _header(headers, "X-YM30-Execution-Id")
    capability_id = _header(headers, "X-YM30-Capability-Id")
    claimed_hash = _header(headers, "X-YM30-Body-SHA256")

    if method.upper() != "POST" or path != "/execute" or protocol != "1.1":
        raise AuthenticationError("invalid_protocol")
    if not settings.ym30_secret:
        raise AuthenticationError("provider_not_configured")
    if key_id != settings.ym30_key_id:
        raise AuthenticationError("invalid_key_id")
    if not all(
        [timestamp_text, nonce, signature, execution_id, capability_id, claimed_hash]
    ):
        raise AuthenticationError("invalid_identity")
    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise AuthenticationError("invalid_timestamp") from exc
    if abs(now - timestamp) > 300:
        raise AuthenticationError("expired_timestamp")

    actual_hash = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(actual_hash, claimed_hash):
        raise AuthenticationError("body_hash_mismatch")

    canonical = "\n".join(
        [
            "YM30-CP-V1.1",
            "POST",
            "/execute",
            timestamp_text,
            nonce,
            key_id,
            execution_id,
            capability_id,
            actual_hash,
        ]
    )
    expected = "v1=" + hmac.new(
        settings.ym30_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationError("signature_mismatch")

    return VerifiedRequest(
        key_id=key_id,
        timestamp=timestamp,
        nonce=nonce,
        execution_id=execution_id,
        capability_id=capability_id,
    )
