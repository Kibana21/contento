"""A5 — the Revision Agent (BRD §26, Standalone §17-18, FR-024/025/049).

Turns "make my photo smaller and add Chinese under the greeting" into a short list of
typed edit operations. It cannot write free-form design changes: the operations are the
only vocabulary, and `apply_ops` is deterministic code.

A text edit never calls the image model. Changing a fact edits the campaign's data, so it
re-renders every variation rather than regenerating them.
"""

from __future__ import annotations

from ..contracts.brief import CampaignBrief
from ..contracts.copy import Copy
from ..contracts.design import DesignDoc, PRESETS
from ..contracts.edits import EditPlan, to_edit_ops
from .schemas import EditPlanDraft
from .model_gateway import ModelGateway

INSTRUCTIONS = """
You convert a representative's plain-English change request into edit operations for one
poster. Return only operations; never rewrite the design yourself.

Operations you may use:
  set_copy(field, text)       - reword headline/subheadline/body/cta/signature
  set_fact(field, value)      - correct a campaign fact, e.g. event.date, event.venue
  resize(element_id, scale)   - scale is RELATIVE: 0.8 means 20% smaller, 1.2 means 20% larger
  move_slot(element_id, slot) - move an element to another named slot in this layout
  set_style(element_id, token)- change its type style
  swap_photo(photo_id)        - use a different photo from the profile
  add_translation(language, placement) - add a second language under/over/beside the copy
  set_theme(theme)            - 'bold' (red ground) or 'highlight' (light ground)
  change_preset(preset)       - a different output size, e.g. instagram_story
  toggle_element(element_id, visible) - hide or show an element
  regenerate_asset(element_id, guidance) - only when a NEW image is genuinely required

Rules:
- Use element ids and slots exactly as listed. If the request names something that is not
  there, add it to `unsupported` rather than guessing.
- "Smaller"/"bigger" with no number means 0.85 / 1.2.
- Never use regenerate_asset for a text or layout change: it costs an image generation.
- Never invent facts. If asked for a date or link you were not given, add it to `unsupported`.
- Keep the plan minimal: change only what was asked.
- `interpretation` is one plain line telling the user what will change.
"""


def _context(design: DesignDoc, copy: Copy, brief: CampaignBrief) -> str:
    elements = "\n".join(
        f"  {e.id} ({e.type.value}) in slot '{e.slot}'"
        + (f", shows {e.content_ref}" if e.content_ref else "")
        + (f", currently {e.overrides.get('scale', 1.0):g}x" if "scale" in e.overrides else "")
        for e in design.elements
    )
    slots = sorted({e.slot for e in design.elements})
    photos = ", ".join(sorted({f.field for f in brief.facts if f.field.startswith("event.")})) or "none"
    return "\n".join([
        f"Layout family: {design.layout_family} (theme: {design.theme.value}, "
        f"size: {design.canvas.preset}, language: {design.language})",
        f"Available slots: {', '.join(slots)}",
        "Elements:", elements,
        "Current copy:",
        *(f"  {k}: {v}" for k, v in copy.texts().items()),
        f"Campaign facts that may be corrected: {photos}",
        f"Output presets available: {', '.join(sorted(PRESETS))}",
    ])


async def plan_revision(gateway: ModelGateway, instruction: str, design: DesignDoc,
                        copy: Copy, brief: CampaignBrief) -> EditPlan:
    agent = gateway.agent("revision_agent", tier="fast", output_type=EditPlanDraft,
                          instructions=INSTRUCTIONS)
    prompt = f"{_context(design, copy, brief)}\n\nRepresentative's request:\n{instruction}"
    result = await gateway.run(agent, prompt, node="revision_agent", tier="fast")
    draft = result.output
    ops, rejected = to_edit_ops(draft.ops)
    if not ops:
        rejected.append("nothing in the request maps to a supported change")
    return EditPlan(ops=ops or [], interpretation=draft.interpretation,
                    unsupported=[*draft.unsupported, *rejected]) if ops else EditPlan(
        ops=[], interpretation=draft.interpretation, unsupported=[*draft.unsupported, *rejected])
