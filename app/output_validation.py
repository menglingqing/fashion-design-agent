from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.capability_router import CapabilityRoute
from app.schemas import ExpertOutput


class OutputValidationError(Exception):
    pass


_FENCED_JSON = re.compile(r"\A```(?:json)?\s*(\{.*\})\s*```\Z", re.DOTALL)
_PERFORMANCE_TERM = re.compile(
    r"(防水|防晒|UPF|抗菌|温升|透湿|透气|保暖|可持续|专利)",
    re.IGNORECASE,
)
_NUMERIC_CLAIM = re.compile(r"\d+(?:\.\d+)?\s*(?:mm|%|级|g/m|Pa)", re.IGNORECASE)


def _extract_single_json(raw: str) -> str:
    stripped = raw.strip()
    fenced = _FENCED_JSON.fullmatch(stripped)
    if fenced:
        return fenced.group(1)
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise OutputValidationError("Model output must be a single JSON object")
    return stripped


def _all_text(output: ExpertOutput) -> str:
    parts = [output.summary, output.next_action]
    parts.extend(section.title + "\n" + section.content_markdown for section in output.sections)
    parts.extend(output.decision_log.needs_confirmation)
    parts.extend(check.name + "\n" + check.note for check in output.quality_checks)
    return "\n".join(parts)


def parse_and_validate_output(
    raw: str, route: CapabilityRoute
) -> ExpertOutput:
    try:
        value = json.loads(_extract_single_json(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputValidationError("Model output must be a single JSON object") from exc
    try:
        output = ExpertOutput.model_validate(value)
    except ValidationError as exc:
        raise OutputValidationError("Model output failed schema validation") from exc

    text = _all_text(output)
    if route.route_name == "reference_extension":
        check_text = "\n".join(
            check.name + "\n" + check.note for check in output.quality_checks
        )
        if not (
            "三个可见维度" in check_text
            or "至少三个" in check_text
            or "three visible dimensions" in check_text.lower()
        ):
            raise OutputValidationError(
                "Reference extension must verify three visible dimensions"
            )

    if route.route_name == "visual_brief" and any(
        claim in text for claim in ("生产准确技术图", "可直接下单", "production-accurate")
    ):
        raise OutputValidationError(
            "Visual brief must not claim production accuracy"
        )

    if _PERFORMANCE_TERM.search(text) and _NUMERIC_CLAIM.search(text):
        warnings = [
            check.note
            for check in output.quality_checks
            if check.status == "warning"
        ]
        warnings.extend(output.decision_log.needs_confirmation)
        if not warnings:
            raise OutputValidationError(
                "Unverified performance claim requires a warning"
            )
    return output
