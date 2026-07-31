from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


REFERENCES = ("workflow.md", "templates.md", "quality-checklists.md")


@dataclass(frozen=True)
class CapabilityRoute:
    capability_id: str
    route_name: str
    instruction: str
    reference_files: tuple[str, ...]


_ROUTES = {
    "plan_fashion_collection": CapabilityRoute(
        "plan_fashion_collection",
        "seasonal_planning",
        "围绕季节、胶囊系列、品类与 SKU 架构完成企划，并明确商业角色和评审门。",
        REFERENCES,
    ),
    "develop_apparel_style": CapabilityRoute(
        "develop_apparel_style",
        "single_style",
        "从需求或授权参考完成单款 brief、差异化方向、推荐方案与技术交接内容。",
        REFERENCES,
    ),
    "analyze_and_extend_reference": CapabilityRoute(
        "analyze_and_extend_reference",
        "reference_extension",
        "分析参考款的设计 DNA，执行 retain / transform / avoid，并让每个方向至少改变三个可见维度。",
        REFERENCES,
    ),
    "create_fashion_visual_brief": CapabilityRoute(
        "create_fashion_visual_brief",
        "visual_brief",
        "只交付效果图、技术款式图、细节图或展板的文字定义与生成提示词，不声称已生成生产准确图纸。",
        REFERENCES,
    ),
    "review_apparel_sample": CapabilityRoute(
        "review_apparel_sample",
        "sample_review",
        "按安全、功能、合体、比例、结构、材料、细节与成本顺序给出可观察、可验证的样衣修改意见。",
        REFERENCES,
    ),
    "craft_apparel_product_story": CapabilityRoute(
        "craft_apparel_product_story",
        "product_communication",
        "按用户痛点、设计回应、客观证据、穿着收益与场景组织产品故事和卖点。",
        REFERENCES,
    ),
}

CAPABILITY_ROUTES = MappingProxyType(_ROUTES)


def route_capability(capability_id: str) -> CapabilityRoute:
    try:
        return CAPABILITY_ROUTES[capability_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported capability: {capability_id}") from exc
