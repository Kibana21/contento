"""Folders in, posters out — the free-form counterpart of `src/workflow.py`.

The front half is deliberately identical to the structured engine: the same loaders, the same
Brief Agent, the same policy gate. Only once a campaign is understood and cleared does the
path diverge, and even then the output folder has the same shape, so `campaign.json` answers
"how was this made?" the same way whichever engine produced it.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..ai.artifact_classifier import classify_artifact
from ..ai.brief_agent import BriefDeps, brief_card, build_brief
from ..ai.model_gateway import FREEFORM_MODELS, BudgetExceeded, ModelGateway
from ..ai.reviewers import review_visual
from ..contracts.brief import CampaignBrief
from ..contracts.common import RunBudget, Risk, ValidationReport
from ..contracts.content import ContentSet
from ..contracts.copy import Copy
from ..lineage.record import (ExportRecord, LineageRecord, PageRecord, VariationRecord,
                              build_record, embed_metadata, file_digest)
from ..loaders import load_brand_pack, load_profile, load_request
from ..policy.rules import PolicyDecision
from .graph import CampaignState, VariationResult, run_graph, run_sequential

Progress = Callable[[str], None]

#: Free-form authoring costs several times what filling a template does, so the default
#: ceiling is raised — and still enforced, with partial results on exhaustion.
DEFAULT_BUDGET = RunBudget(max_tokens=250_000, max_images=4, max_model_calls=60)


@dataclass
class FreeformResult:
    campaign_id: str
    out_dir: Path
    brief: CampaignBrief | None = None
    decision: PolicyDecision | None = None
    copy: Copy = field(default_factory=lambda: Copy(headline=""))
    content: ContentSet = field(default_factory=ContentSet)
    variations: list[VariationResult] = field(default_factory=list)
    copy_report: ValidationReport = field(default_factory=ValidationReport)
    lineage: LineageRecord | None = None
    notes: list[str] = field(default_factory=list)
    partial: bool = False
    blocked_reason: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.variations) and not self.blocked_reason

    def summary(self) -> str:
        lines = [f"Campaign {self.campaign_id} -> {self.out_dir}"]
        if self.blocked_reason:
            lines.append(f"  BLOCKED: {self.blocked_reason}")
        for v in self.variations:
            pages = f"{len(v.renders)} page(s)"
            state = "ok" if v.ok else f"{len(v.report.errors)} error(s), {len(v.audit)} audit"
            lines.append(f"  {v.variation_id}  {v.doc.system.name:22} "
                         f"{v.doc.system.archetype:18} {pages:10} {state}")
            for repair in v.repairs[:3]:
                lines.append(f"       repaired: {repair}")
        if self.partial:
            lines.append("  NOTE: stopped early on the budget; showing what was completed")
        for note in self.notes:
            lines.append(f"  · {note}")
        return "\n".join(lines)


async def create_freeform_campaign(
    profile_dir: Path | str,
    campaign_dir: Path | str,
    *,
    out_root: Path | str = "output",
    variations: int = 4,
    interactive: bool = True,
    visual_review: bool = True,
    use_graph: bool = True,
    budget: RunBudget | None = None,
    today: dt.date | None = None,
    progress: Progress = lambda msg: None,
    ask: Callable[[str], str] | None = None,
) -> FreeformResult:
    campaign_dir, profile_dir = Path(campaign_dir), Path(profile_dir)
    campaign_id = f"CAM-{dt.date.today():%Y}-{campaign_dir.name}"
    out_dir = Path(out_root) / campaign_dir.name
    gateway = ModelGateway(budget=budget or DEFAULT_BUDGET.model_copy(),
                           models=dict(FREEFORM_MODELS), campaign_id=campaign_id)
    _clear_previous_run(out_dir)

    progress("loading profile, request and brand pack")
    profile = load_profile(profile_dir)
    request_text, artifacts = load_request(campaign_dir)
    brand = load_brand_pack()
    result = FreeformResult(campaign_id=campaign_id, out_dir=out_dir)

    def prompt_user(question: str) -> str:
        if not interactive:
            return ""
        print(f"\n  ? {question}")
        return input("  > ").strip()

    try:
        if artifacts:
            progress(f"reading {len(artifacts)} upload(s)")
            artifacts = [await classify_artifact(gateway, a) for a in artifacts]

        progress("understanding the request")
        deps = BriefDeps(profile=profile, request_text=request_text, artifacts=artifacts,
                         today=today or dt.date.today(),
                         ask=ask or (prompt_user if interactive else None))
        brief, decision = await build_brief(gateway, deps, campaign_id)
        result.brief, result.decision = brief, decision
        if interactive:
            print("\n" + brief_card(brief, decision) + "\n")
        if brief.content.items:
            progress(f"quoted {sum(brief.content.counts().values())} content item(s) from uploads")

        if not decision.can_generate:
            result.blocked_reason = ("missing required details: "
                                     + ", ".join(decision.missing_blocking))
            _write(result, gateway, request_text, profile.version, brand.version, deps)
            return result

        # The richer engine makes it easy to produce material we are not yet cleared to
        # produce: red risk needs approved sources and human approval, neither of which is
        # built (docs/architecture.md §13). Refuse rather than quietly generate it.
        if decision.risk is Risk.RED:
            result.blocked_reason = (
                "red risk: the free-form engine is limited to green and amber campaigns "
                "until approved-source retrieval and human approval exist")
            _write(result, gateway, request_text, profile.version, brand.version, deps)
            return result

        state: CampaignState = {
            "brief": brief, "decision": decision, "profile": profile, "brand": brand,
            "out_dir": out_dir, "variations": [], "notes": [],
        }
        progress("writing copy and arranging content")
        runner = run_graph if use_graph else run_sequential
        final = await runner(state, gateway, variations=variations)

        result.copy = final.get("copy", result.copy)
        result.content = final.get("content", result.content)
        result.copy_report = final.get("copy_report", result.copy_report)
        result.variations = sorted(final.get("variations", []), key=lambda v: v.variation_id)
        result.notes = final.get("notes", [])
        result.partial = bool(final.get("partial"))

        if visual_review:
            for variation in result.variations:
                if variation.ok and variation.poster_path:
                    try:
                        review = await review_visual(gateway, variation.poster_path,
                                                     direction=variation.doc.system.name)
                        variation.report = variation.report.merge(review)
                    except BudgetExceeded:
                        result.partial = True
                        break
                    except Exception:  # noqa: BLE001 — advisory only, never fails a run
                        pass
    except BudgetExceeded as exc:
        progress("token budget reached")
        result.partial = True
        result.notes.append(f"stopped on the token budget ({exc})")
    except Exception as exc:  # noqa: BLE001 — a partial campaign folder beats a traceback
        result.notes.append(f"run failed: {type(exc).__name__}: {exc}")

    _write(result, gateway, request_text, profile.version, brand.version, deps)
    progress("written")
    return result


def _clear_previous_run(out_dir: Path) -> None:
    """A folder must never mix two runs. Mirrors `workflow._clear_previous_run`."""
    if not out_dir.exists():
        return
    for pattern in ("variation-*", "campaign.json", "usage.json", "brief.json",
                    "policy.json", "copy.json", "content.json"):
        for path in out_dir.glob(pattern):
            path.unlink(missing_ok=True)
    for sub in ("designs", "validation", "exports"):
        for path in (out_dir / sub).glob("*"):
            path.unlink(missing_ok=True)
    pages = out_dir / "pages"
    if pages.exists():
        for child in sorted(pages.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()


def _merge_pdf(variation: VariationResult, out_dir: Path) -> Path | None:
    """One PDF per multi-page variation. `pypdf` is already a dependency."""
    if len(variation.renders) < 2:
        return None
    try:
        from pypdf import PdfWriter
    except ImportError:
        return None
    target = out_dir / "exports" / f"variation-{variation.variation_id}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    try:
        for render in variation.renders:
            pdf = render.image_path.with_suffix(".pdf")
            if pdf.exists():
                writer.append(str(pdf))
        if not writer.pages:
            return None
        with target.open("wb") as handle:
            writer.write(handle)
    except Exception:  # noqa: BLE001 — a missing PDF must not fail the campaign
        return None
    return target


def _write(result: FreeformResult, gateway: ModelGateway, request_text: str,
           profile_version: str, brand_version: str, deps: BriefDeps) -> None:
    out = result.out_dir
    for sub in ("designs", "validation", "exports"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    if result.brief is None or result.decision is None:
        gateway.write_usage(out / "usage.json")
        return

    def dump(name: str, payload) -> None:
        (out / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    dump("brief.json", result.brief.model_dump(mode="json"))
    dump("policy.json", result.decision.model_dump(mode="json"))
    dump("copy.json", result.copy.model_dump(mode="json"))
    dump("content.json", result.content.model_dump(mode="json"))
    (out / "validation" / "copy.json").write_text(
        json.dumps(result.copy_report.model_dump(mode="json"), indent=2, ensure_ascii=False))

    record = build_record(
        campaign_id=result.campaign_id, user=result.brief.agent.profile_id,
        request_text=request_text, brief=result.brief, decision=result.decision,
        copy=result.copy, profile_version=profile_version, brand_version=brand_version,
        models=dict(gateway.models), usage=gateway.usage_log,
        usage_summary=gateway.summary(), questions=deps.questions_asked,
        partial=result.partial)
    record.notes = [*result.notes, *([result.blocked_reason] if result.blocked_reason else [])]

    for variation in result.variations:
        vid = variation.variation_id
        design_path = out / "designs" / f"variation-{vid}.v{variation.doc.version}.json"
        design_path.write_text(json.dumps(variation.doc.model_dump(mode="json"), indent=2,
                                          ensure_ascii=False))
        (out / "validation" / f"variation-{vid}.json").write_text(json.dumps({
            "checks_run": variation.report.checks_run,
            "errors": [f.model_dump(mode="json") for f in variation.report.errors],
            "warnings": [f.model_dump(mode="json") for f in variation.report.findings
                         if f.severity.value == "warn"],
            "audit": [f.model_dump(mode="json") for f in variation.audit],
            "repairs": variation.repairs,
        }, indent=2, ensure_ascii=False))

        pages = [
            PageRecord(index=i + 1, path=str(r.image_path.relative_to(out)),
                       sha256_16=file_digest(r.image_path), width=r.canvas.width,
                       height=r.canvas.height,
                       purpose=variation.doc.pages[i].plan.purpose
                       if i < len(variation.doc.pages) else None,
                       html_path=str(r.html_path.relative_to(out)))
            for i, r in enumerate(variation.renders)
        ]
        if not pages:
            continue

        # page 1 is also published at the top level, so the folder reads the same way
        # whichever engine produced it
        poster = out / f"variation-{vid}.png"
        poster.write_bytes(variation.renders[0].image_path.read_bytes())

        record.variations.append(VariationRecord(
            id=vid, direction=variation.doc.system.model_dump(mode="json"),
            layout_family=variation.doc.system.archetype,
            design_version=variation.doc.version,
            design_path=str(design_path.relative_to(out)),
            poster_path=poster.name,
            validation={"checks_run": variation.report.checks_run,
                        "errors": [f.model_dump(mode="json") for f in variation.report.errors],
                        "warnings": [f.model_dump(mode="json") for f in variation.report.findings
                                     if f.severity.value == "warn"]},
            auto_fixes=variation.repairs,
            reviewer_findings=[f.model_dump(mode="json") for f in variation.report.findings
                               if f.rule_id.startswith("visual.review")],
            design_system=variation.doc.system.model_dump(mode="json"),
            pages=pages, engine="freeform"))

        pdf = _merge_pdf(variation, out)
        record.exports.append(ExportRecord(
            variation=vid, preset=variation.doc.pages[0].plan.preset, format="png",
            path=poster.name, sha256_16=file_digest(poster),
            width=pages[0].width, height=pages[0].height,
            page_count=len(pages), pages=pages,
            pdf_path=str(pdf.relative_to(out)) if pdf else None))

    record.layout_families = sorted({v.doc.system.archetype for v in result.variations})
    record.write(out / "campaign.json")
    gateway.write_usage(out / "usage.json")
    for variation in result.variations:            # provenance travels with the file
        for render in variation.renders:
            embed_metadata(render.image_path, record.stamp())
        if variation.renders:
            embed_metadata(out / f"variation-{variation.variation_id}.png", record.stamp())
    result.lineage = record


def create_freeform_campaign_sync(*args, **kwargs) -> FreeformResult:
    return asyncio.run(create_freeform_campaign(*args, **kwargs))
