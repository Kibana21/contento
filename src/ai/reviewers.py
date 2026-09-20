"""B1/B2 — advisory reviewers. They flag; they never pass a design (ADR-006)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Finding, Severity, Strict, ValidationReport
from ..contracts.copy import Copy
from .model_gateway import ModelGateway

TONE_INSTRUCTIONS = """
You review marketing copy for AIA Singapore against the brand's mentor voice.

A mentor IS: compassionate, straightforward, positive, confident, encouraging, motivating,
guiding, on your side. A mentor IS NOT: harsh, negative, inexperienced, confusing,
judgemental, passive, in charge, arrogant.

Flag only real problems, most important first:
- salesy, pushy or urgent wording
- fear-based framing
- jargon or corporate distance ("customers are advised")
- claims or implied promises about money, returns or coverage
- tone that does not match the campaign (a festive greeting that sounds like a product ad)
- anything that would exclude or stereotype a community

Return an empty list when the copy is fine. Never invent problems, and never approve:
your findings are advisory signals for a human.
"""

VISUAL_INSTRUCTIONS = """
You review a rendered AIA Singapore poster image against brand guidance.

Check: is there one clear focal point and hierarchy; is text legible against its background;
is the portrait cropped naturally; does the layout feel crowded or unbalanced; does imagery
look authentic and people-focused rather than generic AI stock; is anything visually broken.

AIA photography must feel candid and real, show people, avoid single-use plastics, and avoid
posed or stereotyped imagery.

Flag only what you can actually see. Return an empty list if the poster looks right.
"""


class ReviewFinding(Strict):
    issue: str = Field(max_length=160)
    severity: Severity = Severity.WARN
    suggestion: str | None = Field(default=None, max_length=160)
    element: str | None = Field(default=None, description="Which part of the design, if identifiable")


class ReviewOutput(Strict):
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=6)
    overall: str = Field(max_length=200, description="One line on how the piece reads")


def _to_report(out: ReviewOutput, rule_prefix: str) -> ValidationReport:
    return ValidationReport(
        checks_run=1,
        # an advisory reviewer may never raise an error: it flags, a human decides (ADR-006)
        findings=[Finding(rule_id=f"{rule_prefix}.{i}",
                          severity=Severity.INFO if f.severity is Severity.INFO else Severity.WARN,
                          message=f.issue, suggestion=f.suggestion, element_id=f.element)
                  for i, f in enumerate(out.findings)],
    )


async def review_tone(gateway: ModelGateway, copy: Copy, brief: CampaignBrief) -> ValidationReport:
    agent = gateway.agent("tone_reviewer", tier="fast", output_type=ReviewOutput,
                          instructions=TONE_INSTRUCTIONS)
    prompt = (f"Campaign: {brief.family.value}, tone asked for: {', '.join(brief.tone) or 'warm'}\n"
              f"Core message: {brief.story.core_message}\n\n"
              f"Copy:\n" + "\n".join(f"  {k}: {v}" for k, v in copy.texts().items()))
    result = await gateway.run(agent, prompt, node="tone_reviewer", tier="fast")
    return _to_report(result.output, "tone.review")


async def review_visual(gateway: ModelGateway, image_path: Path, *, direction: str = "") -> ValidationReport:
    """Multimodal design review. Gated: only run after the deterministic checks pass."""
    from pydantic_ai import BinaryContent

    agent = gateway.agent("visual_reviewer", tier="vision", output_type=ReviewOutput,
                          instructions=VISUAL_INSTRUCTIONS)
    prompt = [f"Creative direction: {direction or 'unspecified'}. Review this poster.",
              BinaryContent(data=Path(image_path).read_bytes(), media_type="image/png")]
    result = await gateway.run(agent, prompt, node="visual_reviewer", tier="vision")
    return _to_report(result.output, "visual.review")
