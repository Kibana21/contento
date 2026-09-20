"""The V1 pipeline: folders in, posters out (Standalone §6, §19).

Plain Python orchestration on purpose. Every step is explicit and testable, and the
contracts are shaped so this can move onto a workflow engine later without rewriting the
agents (see docs/architecture-plan.md).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .ai.artifact_classifier import classify_artifact
from .ai.brief_agent import BriefDeps, brief_card, build_brief
from .ai.copywriter import write_copy
from .ai.creative_director import choose_directions
from .ai.model_gateway import BudgetExceeded, ModelGateway
from .ai.reviewers import review_tone, review_visual
from .concepts import Concept, build_concept
from .contracts.brief import CampaignBrief
from .contracts.common import RunBudget, ValidationReport
from .contracts.copy import Copy
from .lineage.record import (ExportRecord, LineageRecord, VariationRecord, build_record,
                             embed_metadata, file_digest)
from .loaders import load_brand_pack, load_profile, load_request
from .policy.rules import PolicyDecision
from .validate.copy import validate_copy

Progress = Callable[[str], None]


@dataclass
class CampaignResult:
    campaign_id: str
    out_dir: Path
    brief: CampaignBrief
    decision: PolicyDecision
    copy: Copy
    concepts: list[Concept] = field(default_factory=list)
    copy_report: ValidationReport = field(default_factory=ValidationReport)
    tone_report: ValidationReport = field(default_factory=ValidationReport)
    lineage: LineageRecord | None = None
    partial: bool = False
    blocked_reason: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.concepts) and not self.blocked_reason

    def summary(self) -> str:
        lines = [f"Campaign {self.campaign_id} -> {self.out_dir}"]
        if self.blocked_reason:
            lines.append(f"  BLOCKED: {self.blocked_reason}")
        for c in self.concepts:
            state = "ok" if c.ok else f"{len(c.report.errors)} error(s)"
            warns = len([f for f in c.report.findings if f.severity.value == "warn"])
            lines.append(f"  {c.direction.id}  {c.direction.name:22} {c.direction.layout_family:18} "
                         f"{state}{f', {warns} warning(s)' if warns else ''}")
        if self.partial:
            lines.append("  NOTE: run stopped early on the token budget; showing what was completed")
        return "\n".join(lines)


async def create_campaign(
    profile_dir: Path | str,
    campaign_dir: Path | str,
    *,
    out_root: Path | str = "output",
    preset: str = "instagram_portrait",
    interactive: bool = True,
    images_enabled: bool = True,
    visual_review: bool = True,
    budget: RunBudget | None = None,
    today: dt.date | None = None,
    progress: Progress = lambda msg: None,
    ask: Callable[[str], str] | None = None,
) -> CampaignResult:
    campaign_dir, profile_dir = Path(campaign_dir), Path(profile_dir)
    campaign_id = f"CAM-{dt.date.today():%Y}-{campaign_dir.name}"
    out_dir = Path(out_root) / campaign_dir.name
    gateway = ModelGateway(budget=budget or RunBudget(), campaign_id=campaign_id)
    partial = False
    _clear_previous_run(out_dir)

    # ---- 1. load ---------------------------------------------------------
    progress("loading profile, request and brand pack")
    profile = load_profile(profile_dir)
    request_text, artifacts = load_request(campaign_dir)
    brand = load_brand_pack()
    brief: CampaignBrief | None = None
    decision: PolicyDecision | None = None
    copy = Copy(headline="")
    copy_report = tone_report = ValidationReport()
    concepts: list[Concept] = []

    def prompt_user(question: str) -> str:
        if not interactive:
            return ""
        print(f"\n  ? {question}")
        return input("  > ").strip()

    try:
        # ---- 2. classify uploads -----------------------------------------
        if artifacts:
            progress(f"reading {len(artifacts)} upload(s)")
            artifacts = [await classify_artifact(gateway, a) for a in artifacts]

        # ---- 3. brief + policy -------------------------------------------
        progress("understanding the request")
        deps = BriefDeps(profile=profile, request_text=request_text, artifacts=artifacts,
                         today=today or dt.date.today(), ask=ask or (prompt_user if interactive else None))
        brief, decision = await build_brief(gateway, deps, campaign_id)
        progress("brief ready")
        if interactive:
            print("\n" + brief_card(brief, decision) + "\n")

        if not decision.can_generate:
            result = CampaignResult(campaign_id, out_dir, brief, decision, Copy(headline=""),
                                    blocked_reason=f"missing required details: {', '.join(decision.missing_blocking)}")
            _write_campaign_files(result, gateway, request_text, profile.version, brand.version, deps)
            return result

        # ---- 4. copy ------------------------------------------------------
        progress("writing copy")
        copy = await write_copy(gateway, brief, profile, decision)
        copy_report = validate_copy(copy, brief, decision)
        tone_report = await review_tone(gateway, copy, brief)

        # ---- 5. creative directions ---------------------------------------
        progress("choosing creative directions")
        directions, source = await choose_directions(gateway, brief, copy, profile)
        progress(f"{len(directions.directions)} directions ({source})")

        # ---- 6. concepts ---------------------------------------------------
        for d in directions.directions:
            progress(f"building variation {d.id}: {d.name}")
            try:
                concept = await build_concept(gateway, d, brief, copy, profile, decision, brand,
                                              out_dir, preset=preset, images_enabled=images_enabled)
            except BudgetExceeded:
                partial = True
                progress("token budget reached; keeping the variations already built")
                break
            # the multimodal reviewer is gated behind the deterministic checks (ADR-006)
            if visual_review and concept.ok:
                try:
                    review = await review_visual(gateway, concept.image_path, direction=d.name)
                    concept.report = concept.report.merge(review)
                except BudgetExceeded:
                    partial = True
            concepts.append(concept)

    except BudgetExceeded as exc:
        # out of budget mid-run: keep whatever is finished and say so plainly
        progress("token budget reached")
        result = CampaignResult(campaign_id, out_dir, brief, decision, copy, concepts,
                                copy_report, tone_report, partial=True,
                                blocked_reason=f"stopped on the token budget ({exc})")
        if brief is not None and decision is not None:
            _write_campaign_files(result, gateway, request_text, profile.version, brand.version, deps)
        return result

    result = CampaignResult(campaign_id, out_dir, brief, decision, copy, concepts,
                            copy_report, tone_report, partial=partial)
    _write_campaign_files(result, gateway, request_text, profile.version, brand.version, deps)
    progress("written")
    return result


def _clear_previous_run(out_dir: Path) -> None:
    """Remove artefacts from an earlier run so a folder never mixes two campaigns."""
    if not out_dir.exists():
        return
    for pattern in ("variation-*", "contact-sheet.png", "campaign.json", "usage.json",
                    "brief.json", "policy.json", "copy.json"):
        for path in out_dir.glob(pattern):
            path.unlink(missing_ok=True)
    for sub in ("concepts", "designs", "validation", "generated"):
        for path in (out_dir / sub).glob("*"):
            path.unlink(missing_ok=True)


def _write_campaign_files(result: CampaignResult, gateway: ModelGateway, request_text: str,
                          profile_version: str, brand_version: str, deps: BriefDeps) -> None:
    """Write the self-contained campaign folder (Standalone §16, BRD §36)."""
    out = result.out_dir
    (out / "concepts").mkdir(parents=True, exist_ok=True)
    (out / "designs").mkdir(parents=True, exist_ok=True)
    (out / "validation").mkdir(parents=True, exist_ok=True)

    (out / "brief.json").write_text(json.dumps(result.brief.model_dump(mode="json"), indent=2, ensure_ascii=False))
    (out / "policy.json").write_text(json.dumps(result.decision.model_dump(mode="json"), indent=2))
    (out / "copy.json").write_text(json.dumps(result.copy.model_dump(mode="json"), indent=2, ensure_ascii=False))
    (out / "validation" / "copy.json").write_text(json.dumps(
        {"rules": result.copy_report.model_dump(mode="json"),
         "tone_review": result.tone_report.model_dump(mode="json")}, indent=2, ensure_ascii=False))

    record = build_record(
        campaign_id=result.campaign_id, user=result.brief.agent.profile_id, request_text=request_text,
        brief=result.brief, decision=result.decision, copy=result.copy,
        profile_version=profile_version, brand_version=brand_version,
        models={k: v for k, v in gateway.models.items()},
        usage=gateway.usage_log, usage_summary=gateway.summary(),
        questions=deps.questions_asked, partial=result.partial)
    record.notes = [result.blocked_reason] if result.blocked_reason else []

    for concept in result.concepts:
        cid = concept.direction.id
        (out / "concepts" / f"direction-{cid}.json").write_text(
            json.dumps(concept.direction.model_dump(mode="json"), indent=2, ensure_ascii=False))
        design_path = out / "designs" / f"variation-{cid}.v{concept.design.version}.json"
        design_path.write_text(json.dumps(concept.design.model_dump(mode="json"), indent=2, ensure_ascii=False))
        (out / "validation" / f"variation-{cid}.json").write_text(
            json.dumps(concept.report.model_dump(mode="json"), indent=2, ensure_ascii=False))

        record.variations.append(VariationRecord(
            id=cid, direction=concept.direction.model_dump(mode="json"),
            layout_family=concept.design.layout_family, design_version=concept.design.version,
            design_path=str(design_path.relative_to(out)), poster_path=str(concept.image_path.relative_to(out)),
            background={"kind": concept.design.background.kind, "asset": concept.design.background.asset,
                        "note": concept.background_note},
            validation={"checks_run": concept.report.checks_run,
                        "errors": [f.model_dump(mode="json") for f in concept.report.errors],
                        "warnings": [f.model_dump(mode="json") for f in concept.report.findings
                                     if f.severity.value == "warn"]},
            auto_fixes=concept.fixes_applied,
            reviewer_findings=[f.model_dump(mode="json") for f in concept.report.findings
                               if f.rule_id.startswith(("tone.review", "visual.review"))]))
        record.exports.append(ExportRecord(
            variation=cid, preset=concept.design.canvas.preset, format=concept.render.format,
            path=str(concept.image_path.relative_to(out)), sha256_16=file_digest(concept.image_path),
            width=concept.design.canvas.width, height=concept.design.canvas.height))

    record.layout_families = sorted({c.design.layout_family for c in result.concepts})
    record.write(out / "campaign.json")
    gateway.write_usage(out / "usage.json")
    for concept in result.concepts:  # provenance travels with the file
        embed_metadata(concept.image_path, record.stamp())
    result.lineage = record


def create_campaign_sync(*args, **kwargs) -> CampaignResult:
    return asyncio.run(create_campaign(*args, **kwargs))
