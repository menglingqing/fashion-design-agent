from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectContext(StrictModel):
    brand_positioning: str = ""
    target_wearer: str = ""
    season_market: str = ""
    category: str = ""
    wearing_scenario: str = ""
    price_band: str = ""
    commercial_role: str = ""
    deadline_or_launch_wave: str = ""


class ReferenceItem(StrictModel):
    type: Literal["text"] = "text"
    content: str
    authorization: Literal["user_owned_or_authorized", "unknown"] = "unknown"


class DesignConstraints(StrictModel):
    must_keep: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    production: list[str] = Field(default_factory=list)


class CapabilityInput(StrictModel):
    request: str = Field(min_length=1)
    project_context: ProjectContext = Field(default_factory=ProjectContext)
    references: list[ReferenceItem] = Field(default_factory=list)
    constraints: DesignConstraints = Field(default_factory=DesignConstraints)
    response_language: str = "zh-CN"


class OutputSection(StrictModel):
    title: str
    content_markdown: str


class DecisionLog(StrictModel):
    confirmed_facts: list[str]
    assumptions: list[str]
    needs_confirmation: list[str]
    changes: list[str]


class QualityCheck(StrictModel):
    name: str
    status: Literal["pass", "warning", "not_applicable"]
    note: str


class ExpertOutput(StrictModel):
    summary: str
    route: str
    version: str
    sections: list[OutputSection]
    decision_log: DecisionLog
    quality_checks: list[QualityCheck]
    next_action: str


class ExecutionEnvelope(StrictModel):
    protocol_version: str
    execution_id: str
    trace_id: str
    capability_id: str
    tenant_id: str
    employee_id: str
    execution_mode: Literal["sync"]
    input: dict[str, Any]
    conversation_context: dict[str, Any] = Field(default_factory=dict)
    data_api: dict[str, Any] = Field(default_factory=dict)
    issued_at: int
    deadline_at: int


class YM30Response(StrictModel):
    status: Literal[
        "success", "error", "clarification_required", "cancelled"
    ]
    output: ExpertOutput | dict[str, Any] | None = None
    error: dict[str, Any] | None = None
