from pathlib import Path

import pytest

from app.capability_router import CapabilityRoute, route_capability
from app.prompt_loader import EXPERT_ROOT, load_expert_prompt


def test_prompt_contains_core_guardrails_and_route_instruction() -> None:
    prompt = load_expert_prompt(
        route_capability("analyze_and_extend_reference")
    )
    assert "证据、推断和建议" in prompt
    assert "retain / transform / avoid" in prompt
    assert "至少改变三个可见维度" in prompt
    assert "quality-checklists.md" in prompt
    assert "JSON 外不要输出任何文字" in prompt


def test_route_cannot_escape_reference_directory() -> None:
    malicious = CapabilityRoute(
        capability_id="x",
        route_name="x",
        instruction="x",
        reference_files=("../../secret",),
    )
    with pytest.raises(ValueError, match="Unsafe reference"):
        load_expert_prompt(malicious)


def test_expert_bundle_is_self_contained() -> None:
    expected = {
        Path("SYSTEM_PROMPT.md"),
        Path("SKILL.md"),
        Path("references/workflow.md"),
        Path("references/templates.md"),
        Path("references/quality-checklists.md"),
    }
    actual = {
        path.relative_to(EXPERT_ROOT)
        for path in EXPERT_ROOT.rglob("*")
        if path.is_file()
    }
    assert expected <= actual
