import json
from pathlib import Path


MANIFEST = Path(__file__).resolve().parent.parent / "manifest" / "ym30-manifest.json"
EXPECTED = {
    "plan_fashion_collection",
    "develop_apparel_style",
    "analyze_and_extend_reference",
    "create_fashion_visual_brief",
    "review_apparel_sample",
    "craft_apparel_product_story",
}
OUTPUT_REQUIRED = {
    "summary",
    "route",
    "version",
    "sections",
    "decision_log",
    "quality_checks",
    "next_action",
}


def test_manifest_declares_six_low_risk_capabilities() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value["name"] == "ym30.fashion-design-expert"
    assert value["display_name"] == "服装设计专家"
    assert value["version"] == "1.0.0"
    assert {item["id"] for item in value["capabilities"]} == EXPECTED
    for item in value["capabilities"]:
        assert item["required_permissions"] == {"data": [], "tools": []}
        assert item["write_back"] == []
        assert item["risk_level"] == "low"
        assert "request" in item["input_schema"]["required"]
        assert set(item["output_schema"]["required"]) == OUTPUT_REQUIRED
        assert "$ref" not in json.dumps(item)
