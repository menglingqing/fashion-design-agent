import pytest
from pydantic import ValidationError

from app.capability_router import CAPABILITY_ROUTES, route_capability
from app.schemas import CapabilityInput, ExpertOutput


EXPECTED = {
    "plan_fashion_collection",
    "develop_apparel_style",
    "analyze_and_extend_reference",
    "create_fashion_visual_brief",
    "review_apparel_sample",
    "craft_apparel_product_story",
}


def test_all_six_capabilities_are_stable() -> None:
    assert set(CAPABILITY_ROUTES) == EXPECTED
    assert route_capability("develop_apparel_style").reference_files == (
        "workflow.md",
        "templates.md",
        "quality-checklists.md",
    )


def test_unknown_capability_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported capability"):
        route_capability("unknown")


def test_request_is_required_and_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        CapabilityInput.model_validate({})
    with pytest.raises(ValidationError):
        CapabilityInput.model_validate({"request": "做一件外套", "unexpected": True})


def test_expert_output_has_stable_contract() -> None:
    output = ExpertOutput.model_validate(
        {
            "summary": "完成",
            "route": "single_style",
            "version": "V0 concept",
            "sections": [{"title": "方案", "content_markdown": "内容"}],
            "decision_log": {
                "confirmed_facts": [],
                "assumptions": [],
                "needs_confirmation": [],
                "changes": [],
            },
            "quality_checks": [
                {"name": "一致性", "status": "pass", "note": "已检查"}
            ],
            "next_action": "确认方向",
        }
    )
    assert output.quality_checks[0].status == "pass"
