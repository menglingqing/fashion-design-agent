import json

import pytest

from app.capability_router import route_capability
from app.output_validation import OutputValidationError, parse_and_validate_output


def valid_output() -> dict[str, object]:
    return {
        "summary": "完成设计分析",
        "route": "reference_extension",
        "version": "V0 concept",
        "sections": [
            {
                "title": "差异化方向",
                "content_markdown": "调整廓形、门襟、袖型三个可见维度。",
            }
        ],
        "decision_log": {
            "confirmed_facts": ["用户提供文字参考"],
            "assumptions": [],
            "needs_confirmation": [],
            "changes": [],
        },
        "quality_checks": [
            {
                "name": "参考差异化",
                "status": "pass",
                "note": "已改变廓形、门襟、袖型至少三个可见维度",
            }
        ],
        "next_action": "确认推荐方向",
    }


def test_valid_json_and_exact_code_fence_are_accepted() -> None:
    raw = json.dumps(valid_output(), ensure_ascii=False)
    route = route_capability("analyze_and_extend_reference")
    assert parse_and_validate_output(raw, route).summary == "完成设计分析"
    assert parse_and_validate_output(f"```json\n{raw}\n```", route).summary == "完成设计分析"


def test_prose_outside_json_is_rejected() -> None:
    raw = json.dumps(valid_output(), ensure_ascii=False)
    with pytest.raises(OutputValidationError, match="single JSON object"):
        parse_and_validate_output(
            "这是结果：\n" + raw,
            route_capability("analyze_and_extend_reference"),
        )


def test_missing_required_field_is_rejected() -> None:
    value = valid_output()
    value.pop("next_action")
    with pytest.raises(OutputValidationError, match="schema"):
        parse_and_validate_output(
            json.dumps(value, ensure_ascii=False),
            route_capability("analyze_and_extend_reference"),
        )


def test_reference_route_requires_three_dimension_check() -> None:
    value = valid_output()
    value["quality_checks"] = []
    with pytest.raises(OutputValidationError, match="three visible dimensions"):
        parse_and_validate_output(
            json.dumps(value, ensure_ascii=False),
            route_capability("analyze_and_extend_reference"),
        )


def test_visual_route_rejects_production_accuracy_claim() -> None:
    value = valid_output()
    value["route"] = "visual_brief"
    value["sections"] = [
        {"title": "图纸", "content_markdown": "已经生成生产准确技术图，可直接下单。"}
    ]
    with pytest.raises(OutputValidationError, match="production accuracy"):
        parse_and_validate_output(
            json.dumps(value, ensure_ascii=False),
            route_capability("create_fashion_visual_brief"),
        )


def test_unverified_performance_claim_requires_warning() -> None:
    value = valid_output()
    value["route"] = "product_communication"
    value["sections"] = [
        {"title": "卖点", "content_markdown": "防水等级达到 20000mm。"}
    ]
    with pytest.raises(OutputValidationError, match="performance claim"):
        parse_and_validate_output(
            json.dumps(value, ensure_ascii=False),
            route_capability("craft_apparel_product_story"),
        )
