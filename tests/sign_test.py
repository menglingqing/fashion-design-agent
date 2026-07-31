from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Mapping
import urllib.request
import uuid


def build_signed_request(
    *,
    capability_id: str,
    request_text: str,
    execution_id: str,
    trace_id: str,
    tenant_id: str,
    employee_id: str,
    timestamp: int,
    nonce: str,
    env: Mapping[str, str] | None = None,
) -> tuple[bytes, dict[str, str]]:
    source = os.environ if env is None else env
    key_id = source.get("YM30_PROVIDER_KEY_ID", "")
    secret = source.get("YM30_PROVIDER_SECRET", "")
    if not key_id or not secret:
        raise ValueError(
            "YM30_PROVIDER_KEY_ID and YM30_PROVIDER_SECRET are required"
        )
    payload = {
        "protocol_version": "1.1",
        "execution_id": execution_id,
        "trace_id": trace_id,
        "capability_id": capability_id,
        "tenant_id": tenant_id,
        "employee_id": employee_id,
        "execution_mode": "sync",
        "input": {"request": request_text},
        "conversation_context": {},
        "data_api": {},
        "issued_at": timestamp,
        "deadline_at": timestamp + 90,
    }
    body = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            "YM30-CP-V1.1",
            "POST",
            "/execute",
            str(timestamp),
            nonce,
            key_id,
            execution_id,
            capability_id,
            body_hash,
        ]
    )
    signature = "v1=" + hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-YM30-Protocol-Version": "1.1",
        "X-YM30-Key-Id": key_id,
        "X-YM30-Timestamp": str(timestamp),
        "X-YM30-Nonce": nonce,
        "X-YM30-Signature": signature,
        "X-YM30-Execution-Id": execution_id,
        "X-YM30-Capability-Id": capability_id,
        "X-YM30-Body-SHA256": body_hash,
        "X-YM30-Trace-Id": trace_id,
        "Idempotency-Key": execution_id,
    }
    return body, headers


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a signed YM30 test request")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--capability", default="develop_apparel_style"
    )
    parser.add_argument(
        "--request", default="请为城市通勤夹克制定设计方向"
    )
    args = parser.parse_args()

    execution_id = str(uuid.uuid4())
    body, headers = build_signed_request(
        capability_id=args.capability,
        request_text=args.request,
        execution_id=execution_id,
        trace_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        employee_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        nonce=secrets.token_urlsafe(18),
    )
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/execute",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
