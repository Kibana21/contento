"""Revision flow: load a finished campaign, change only what was asked, re-render.

Standalone §18: do not regenerate the brief, rewrite all copy or regenerate imagery for a
small change. Design-scoped edits touch one variation; campaign-scoped edits (a corrected
fact, new wording, an added language) re-render every variation from the same assets.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .ai.model_gateway import ModelGateway
from .ai.revision_agent import plan_revision
from .contracts.brief import CampaignBrief
from .contracts.common import Fact, RunBudget, ValidationReport
from .contracts.copy import Copy
from .contracts.design import DesignDoc
from .contracts.edits import IMPLEMENTED_OPS, NOT_YET_IMPLEMENTED, EditPlan, apply_ops
from .lineage.record import embed_metadata
from .loaders import load_brand_pack, load_profile
from .policy.rules import PolicyDecision, decide
from .render.context import RenderContext
from .render.renderer import render_async
from .validate import validate_all
from .validate.copy import validate_copy


@dataclass
class RevisionResult:
    variation: str
    plan: EditPlan
    design: DesignDoc
    report: ValidationReport
    poster_path: Path
    copy_changed: bool = False
    facts_changed: list[str] = field(default_factory=list)
    also_rerendered: list[str] = field(default_factory=list)
    used_image_model: bool = False

    def summary(self) -> str:
        lines = [f"Variation {self.variation} -> v{self.design.version}: {self.plan.interpretation}"]
        lines += [f"  - {op.op}: " + ", ".join(f"{k}={v}" for k, v in op.model_dump().items() if k != "op")
                  for op in self.plan.ops]
        if self.facts_changed:
            lines.append(f"  facts corrected: {', '.join(self.facts_changed)}")
        if self.also_rerendered:
            lines.append(f"  other variations re-rendered: {', '.join(self.also_rerendered)}")
        if self.plan.unsupported:
            lines.append(f"  could not do: {'; '.join(self.plan.unsupported)}")
        errors = [f.message for f in self.report.errors]
        if not self.plan.ops:
            lines.append("  nothing was changed")
        lines.append(f"  validation: {'passed' if not errors else '; '.join(errors)}")
        return "\n".join(lines)


def _load(out_dir: Path) -> tuple[CampaignBrief, Copy, PolicyDecision, dict]:
    brief = CampaignBrief.model_validate_json((out_dir / "brief.json").read_text())
    copy = Copy.model_validate_json((out_dir / "copy.json").read_text())
    decision = PolicyDecision.model_validate_json((out_dir / "policy.json").read_text())
    record = json.loads((out_dir / "campaign.json").read_text())
    return brief, copy, decision, record


def _latest_design(out_dir: Path, variation: str) -> DesignDoc:
    files = sorted((out_dir / "designs").glob(f"variation-{variation}.v*.json"),
                   key=lambda p: int(p.stem.split(".v")[-1]))
    if not files:
        raise FileNotFoundError(f"no design for variation {variation!r} in {out_dir}")
    return DesignDoc.model_validate_json(files[-1].read_text())


def _apply_campaign_ops(plan: EditPlan, brief: CampaignBrief, copy: Copy) -> tuple[bool, list[str]]:
    """Copy and fact edits change shared campaign data, not one design."""
    copy_changed = False
    facts: list[str] = []
    for op in plan.ops:
        if op.op == "set_copy":
            setattr(copy, op.field, op.text)
            copy_changed = True
        elif op.op == "set_fact":
            existing = brief.fact(op.field)
            value = op.value
            if op.field == "event.date" and isinstance(value, str):
                try:
                    value = dt.date.fromisoformat(value)
                except ValueError:
                    pass
            if existing:
                brief.facts = [Fact(field=f.field, value=value if f.field == op.field else f.value,
                                    source="user" if f.field == op.field else f.source)
                               for f in brief.facts]
            else:
                brief.facts.append(Fact(field=op.field, value=value, source="user"))
            if brief.event and op.field.startswith("event."):
                setattr(brief.event, op.field.split(".", 1)[1], value)
            facts.append(op.field)
    return copy_changed, facts


async def revise_campaign(
    out_dir: Path | str,
    variation: str,
    instruction: str,
    *,
    profile_dir: Path | str = "profiles/demo-agent",
    budget: RunBudget | None = None,
    gateway: ModelGateway | None = None,
) -> RevisionResult:
    out_dir = Path(out_dir)
    brief, copy, decision, record = _load(out_dir)
    profile, brand = load_profile(profile_dir), load_brand_pack()
    design = _latest_design(out_dir, variation)
    gateway = gateway or ModelGateway(budget=budget or RunBudget(max_tokens=15_000, max_images=1),
                                      campaign_id=brief.campaign_id)

    plan = await plan_revision(gateway, instruction, design, copy, brief)

    # keep only what the pipeline can really do, and say so about the rest
    doable = [op for op in plan.ops if op.op in IMPLEMENTED_OPS]
    for op in plan.ops:
        if op.op not in IMPLEMENTED_OPS:
            plan.unsupported.append(NOT_YET_IMPLEMENTED.get(op.op, f"{op.op} is not supported"))
    plan.ops = doable

    copy_changed, facts_changed = _apply_campaign_ops(plan, brief, copy)

    if copy_changed:  # re-check the words before they reach a poster
        report = validate_copy(copy, brief, decision)
        if not report.passed:
            plan.unsupported.append("copy change rejected: "
                                    + "; ".join(f.message for f in report.errors))
            copy, copy_changed = Copy.model_validate_json((out_dir / "copy.json").read_text()), False
    if facts_changed:
        decision = decide(brief, request_text=record.get("request_text", ""))

    design = apply_ops(design, plan.ops)
    ctx = RenderContext(design=design, brief=brief, copy=copy, profile=profile, brand=brand,
                        decision=decision)
    render = await render_async(ctx, out_dir, name=f"variation-{variation}")
    report = validate_all(design, render.geometry, render.image_path, brand)

    # shared data changed: every other variation must show it too
    also: list[str] = []
    if copy_changed or facts_changed:
        for other in sorted({p.stem.split(".v")[0].split("-")[-1]
                             for p in (out_dir / "designs").glob("variation-*.json")} - {variation}):
            other_design = _latest_design(out_dir, other)
            other_ctx = RenderContext(design=other_design, brief=brief, copy=copy, profile=profile,
                                      brand=brand, decision=decision)
            await render_async(other_ctx, out_dir, name=f"variation-{other}")
            also.append(other)

    # persist
    (out_dir / "designs" / f"variation-{variation}.v{design.version}.json").write_text(
        json.dumps(design.model_dump(mode="json"), indent=2, ensure_ascii=False))
    (out_dir / "validation" / f"variation-{variation}.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    if copy_changed:
        (out_dir / "copy.json").write_text(json.dumps(copy.model_dump(mode="json"), indent=2, ensure_ascii=False))
    if facts_changed:
        (out_dir / "brief.json").write_text(json.dumps(brief.model_dump(mode="json"), indent=2, ensure_ascii=False))
        (out_dir / "policy.json").write_text(json.dumps(decision.model_dump(mode="json"), indent=2))

    record.setdefault("revisions", []).append({
        "at": dt.datetime.now().isoformat(timespec="seconds"), "variation": variation,
        "instruction": instruction, "interpretation": plan.interpretation,
        "ops": [op.model_dump(mode="json") for op in plan.ops],
        "unsupported": plan.unsupported, "design_version": design.version,
        "also_rerendered": also, "usage": gateway.summary()})
    (out_dir / "campaign.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
    embed_metadata(render.image_path, {**{k: str(v) for k, v in record.get("stamp", {}).items()},
                                       "CampaignID": brief.campaign_id, "Revision": str(design.version)})

    return RevisionResult(variation=variation, plan=plan, design=design, report=report,
                          poster_path=render.image_path, copy_changed=copy_changed,
                          facts_changed=facts_changed, also_rerendered=also,
                          used_image_model=plan.needs_image_model)
