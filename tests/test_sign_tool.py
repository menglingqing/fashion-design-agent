import hashlib
import hmac
import json
from pathlib import Path

from tests.sign_test import build_signed_request


def test_build_signed_request_is_deterministic_and_protocol_compliant() -> None:
    env = {
        "YM30_PROVIDER_KEY_ID": "cp_test",
        "YM30_PROVIDER_SECRET": "test-secret",
    }
    body, headers = build_signed_request(
        capability_id="develop_apparel_style",
        request_text="设计城市通勤夹克",
        execution_id="exec-test",
        trace_id="trace-test",
        tenant_id="tenant-test",
        employee_id="employee-test",
        timestamp=1_785_460_000,
        nonce="nonce-test",
        env=env,
    )
    value = json.loads(body)
    assert value["input"]["request"] == "设计城市通勤夹克"
    assert body == json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert headers["Idempotency-Key"] == "exec-test"
    assert headers["X-YM30-Trace-Id"] == "trace-test"

    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            "YM30-CP-V1.1",
            "POST",
            "/execute",
            "1785460000",
            "nonce-test",
            "cp_test",
            "exec-test",
            "develop_apparel_style",
            body_hash,
        ]
    )
    expected = "v1=" + hmac.new(
        b"test-secret", canonical.encode(), hashlib.sha256
    ).hexdigest()
    assert headers["X-YM30-Signature"] == expected


def test_packaging_files_cover_secure_deployment() -> None:
    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "Python 3.11" in readme
    assert "轮换" in readme
    assert "Secret Manager" in readme
    assert "tenant" in readme
    assert "USER app" in dockerfile
    assert "uvicorn" in dockerfile
