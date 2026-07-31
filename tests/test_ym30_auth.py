import hashlib
import hmac

import pytest

from app.config import Settings
from app.ym30_auth import AuthenticationError, verify_request


NOW = 1_785_460_000
BODY = b'{"input":{"request":"design a jacket"}}'


def settings() -> Settings:
    return Settings(
        ym30_key_id="cp_test",
        ym30_secret="unit-test-secret",
        doubao_api_key="x",
        doubao_model="ep-test",
    )


def signed_headers(
    body: bytes = BODY,
    timestamp: int = NOW,
    key_id: str = "cp_test",
    execution_id: str = "exec-test",
    capability_id: str = "develop_apparel_style",
) -> dict[str, str]:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            "YM30-CP-V1.1",
            "POST",
            "/execute",
            str(timestamp),
            "nonce-test",
            key_id,
            execution_id,
            capability_id,
            body_hash,
        ]
    )
    signature = "v1=" + hmac.new(
        b"unit-test-secret", canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "X-YM30-Protocol-Version": "1.1",
        "X-YM30-Key-Id": key_id,
        "X-YM30-Timestamp": str(timestamp),
        "X-YM30-Nonce": "nonce-test",
        "X-YM30-Signature": signature,
        "X-YM30-Execution-Id": execution_id,
        "X-YM30-Capability-Id": capability_id,
        "X-YM30-Body-SHA256": body_hash,
    }


def test_valid_signature_returns_verified_identity() -> None:
    verified = verify_request(
        method="POST",
        path="/execute",
        headers=signed_headers(),
        body=BODY,
        settings=settings(),
        now=NOW,
    )
    assert verified.execution_id == "exec-test"
    assert verified.capability_id == "develop_apparel_style"
    assert verified.nonce == "nonce-test"


@pytest.mark.parametrize(
    ("headers", "body", "now", "category"),
    [
        (signed_headers(), BODY + b" ", NOW, "body_hash_mismatch"),
        (signed_headers(), BODY, NOW + 301, "expired_timestamp"),
        (signed_headers(key_id="wrong"), BODY, NOW, "invalid_key_id"),
    ],
)
def test_invalid_requests_are_rejected(
    headers: dict[str, str], body: bytes, now: int, category: str
) -> None:
    with pytest.raises(AuthenticationError) as error:
        verify_request(
            method="POST",
            path="/execute",
            headers=headers,
            body=body,
            settings=settings(),
            now=now,
        )
    assert error.value.category == category


def test_auth_error_never_exposes_secret_or_signature() -> None:
    headers = signed_headers()
    headers["X-YM30-Signature"] = "v1=bad"
    with pytest.raises(AuthenticationError) as error:
        verify_request(
            method="POST",
            path="/execute",
            headers=headers,
            body=BODY,
            settings=settings(),
            now=NOW,
        )
    rendered = str(error.value)
    assert "unit-test-secret" not in rendered
    assert "v1=bad" not in rendered
