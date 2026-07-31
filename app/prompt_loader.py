from __future__ import annotations

from pathlib import Path

from app.capability_router import CapabilityRoute


EXPERT_ROOT = Path(__file__).resolve().parent.parent / "expert"
REFERENCE_ROOT = EXPERT_ROOT / "references"
ALLOWED_REFERENCES = {
    "workflow.md",
    "templates.md",
    "quality-checklists.md",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_expert_prompt(route: CapabilityRoute) -> str:
    chunks = [
        "=== SYSTEM_PROMPT.md ===\n" + _read(EXPERT_ROOT / "SYSTEM_PROMPT.md"),
        "=== ROUTE ===\n"
        + f"route_name: {route.route_name}\n"
        + f"instruction: {route.instruction}",
        "=== SKILL.md ===\n" + _read(EXPERT_ROOT / "SKILL.md"),
    ]
    for name in route.reference_files:
        if Path(name).name != name or name not in ALLOWED_REFERENCES:
            raise ValueError(f"Unsafe reference: {name}")
        chunks.append(f"=== references/{name} ===\n" + _read(REFERENCE_ROOT / name))
    return "\n\n".join(chunks)
