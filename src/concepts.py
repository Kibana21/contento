"""Concept builder — one creative direction becomes one validated poster.

Order matters: build the design, generate only the assets it actually needs, render,
then check with rules before spending anything on a model reviewer (ADR-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ai.model_gateway import ModelGateway
from .assets.background import generate_background
from .contracts.brand import BrandPack
from .contracts.brief import CampaignBrief
from .contracts.common import ValidationReport
from .contracts.copy import Copy
from .contracts.creative import BackgroundKind, CreativeDirection
from .contracts.design import DesignDoc
from .contracts.profile import AgentProfile
from .policy.rules import PolicyDecision
from .render.context import RenderContext
from .render.design_builder import build_design
from .render.renderer import RenderResult, render_async
from .validate import validate_all

MAX_FIXES = 2


@dataclass
class Concept:
    direction: CreativeDirection
    design: DesignDoc
    render: RenderResult
    report: ValidationReport
    background_note: str | None = None
    fixes_applied: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.report.passed

    @property
    def image_path(self) -> Path:
        return self.render.image_path


def _auto_fix(design: DesignDoc, report: ValidationReport,
              geometry: dict | None = None) -> tuple[DesignDoc, list[str]]:
    """Deterministic repairs for the failures we know how to correct.

    Overflow is fixed by *measurement*: shrink by exactly the ratio the rendered page
    reported, rather than guessing a fixed step.
    """
    applied: list[str] = []
    data = design.model_dump()
    elements = {e["id"]: e for e in data["elements"]}
    measured = {e["id"]: e for e in (geometry or {}).get("elements", [])}
    for finding in report.errors:
        el = elements.get(finding.element_id or "")
        if el is None:
            continue
        if finding.rule_id == "layout.text_collision":
            el["overrides"]["scale"] = float(el["overrides"].get("scale", 1.0)) * 0.88
            applied.append(f"{el['id']}: reduced to clear the overlap")
        elif finding.rule_id in {"layout.overflow", "layout.outside_canvas"}:
            node = measured.get(el["id"])
            ratio = 0.85
            if node and node.get("scrollWidth") and node.get("width"):
                by_width = node["width"] / max(node["scrollWidth"], 1)
                by_height = node["height"] / max(node["scrollHeight"], 1)
                ratio = max(0.55, min(0.96, min(by_width, by_height) * 0.98))
            el["overrides"]["scale"] = float(el["overrides"].get("scale", 1.0)) * ratio
            applied.append(f"{el['id']}: scaled to {ratio:.0%} to fit ({finding.rule_id})")
        elif finding.rule_id == "type.min_size":
            el["overrides"]["scale"] = float(el["overrides"].get("scale", 1.0)) * 1.3
            applied.append(f"{el['id']}: enlarged ({finding.rule_id})")
        elif finding.rule_id == "contrast.text":
            if el["overrides"].pop("colour", None) is None:
                continue  # the colour comes from the layout family: code cannot fix it here
            applied.append(f"{el['id']}: reverted to a brand text colour ({finding.rule_id})")
        elif finding.rule_id == "logo.colour":
            el["overrides"]["colour"] = "white" if data["theme"] == "bold" else "red"
            applied.append(f"{el['id']}: logo colour corrected")
    if not applied:
        return design, []
    data["elements"] = list(elements.values())
    return DesignDoc.model_validate(data), applied


async def build_concept(
    gateway: ModelGateway,
    direction: CreativeDirection,
    brief: CampaignBrief,
    copy: Copy,
    profile: AgentProfile,
    decision: PolicyDecision,
    brand: BrandPack,
    out_dir: Path,
    *,
    preset: str = "instagram_portrait",
    images_enabled: bool = True,
) -> Concept:
    background_asset: str | None = None
    note: str | None = None
    if direction.background is BackgroundKind.GENERATED:
        result = await generate_background(gateway, direction, brief, brand, out_dir / "generated",
                                           aspect_ratio="3:4", enabled=images_enabled)
        background_asset = str(result.path) if result.ok else None
        note = result.skipped_reason

    design = build_design(brief, copy, direction, profile, decision, brand,
                          preset=preset, background_asset=background_asset)

    fixes: list[str] = []
    previous_errors: set[str] | None = None
    for _ in range(MAX_FIXES + 1):
        ctx = RenderContext(design=design, brief=brief, copy=copy, profile=profile,
                            brand=brand, decision=decision)
        render = await render_async(ctx, out_dir, name=f"variation-{direction.id}")
        report = validate_all(design, render.geometry, render.image_path, brand)
        if report.passed:
            break
        signature = {f"{f.rule_id}:{f.element_id}" for f in report.errors}
        if signature == previous_errors:
            break  # the repair is not helping; report honestly rather than loop
        previous_errors = signature
        design, applied = _auto_fix(design, report, render.geometry)
        if not applied:
            break
        fixes += applied

    return Concept(direction=direction, design=design, render=render, report=report,
                   background_note=note, fixes_applied=fixes)
