"""Edit operations — the only way a model may change a design (BRD §26, FR-025/049).

The Revision Agent emits EditOps; `apply_ops` is pure deterministic code.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter

from .common import FactValue, Strict
from .design import Canvas, DesignDoc, ElementType


class SetCopy(Strict):
    op: Literal["set_copy"] = "set_copy"
    field: Literal["headline", "subheadline", "body", "cta", "signature"]
    text: str


class SetFact(Strict):
    op: Literal["set_fact"] = "set_fact"
    field: str
    value: FactValue


class Resize(Strict):
    op: Literal["resize"] = "resize"
    element_id: str
    scale: float = Field(gt=0.2, le=3.0, description="Relative to current size, e.g. 0.8 = 20% smaller")


class MoveSlot(Strict):
    op: Literal["move_slot"] = "move_slot"
    element_id: str
    slot: str


class SetStyle(Strict):
    op: Literal["set_style"] = "set_style"
    element_id: str
    style_token: str


class SwapPhoto(Strict):
    op: Literal["swap_photo"] = "swap_photo"
    photo_id: str


class AddTranslation(Strict):
    op: Literal["add_translation"] = "add_translation"
    language: str
    placement: Literal["below", "above", "beside"] = "below"


class SetTheme(Strict):
    op: Literal["set_theme"] = "set_theme"
    theme: Literal["bold", "highlight"]


class ChangePreset(Strict):
    op: Literal["change_preset"] = "change_preset"
    preset: str


class ToggleElement(Strict):
    op: Literal["toggle_element"] = "toggle_element"
    element_id: str
    visible: bool


class RegenerateAsset(Strict):
    op: Literal["regenerate_asset"] = "regenerate_asset"
    element_id: str
    guidance: str | None = None


EditOp = Annotated[
    Union[SetCopy, SetFact, Resize, MoveSlot, SetStyle, SwapPhoto, AddTranslation,
          SetTheme, ChangePreset, ToggleElement, RegenerateAsset],
    Field(discriminator="op"),
]

EditOpAdapter: TypeAdapter[EditOp] = TypeAdapter(EditOp)

#: Operations the pipeline can actually carry out today. Anything else is reported back to
#: the user rather than silently ignored (bilingual copy needs the Translator, Phase 2).
IMPLEMENTED_OPS = {"set_copy", "set_fact", "resize", "move_slot", "set_style", "swap_photo",
                   "set_theme", "change_preset", "toggle_element"}
NOT_YET_IMPLEMENTED = {
    "add_translation": "a second language is not available yet (Phase 2: approved translations)",
    "regenerate_asset": "regenerating a single image is not available yet",
}

#: Ops that require a new image-model call. Everything else is free.
COSTLY_OPS = {"regenerate_asset"}
#: Ops that change shared campaign data and therefore affect every variation.
CAMPAIGN_WIDE_OPS = {"set_fact", "set_copy", "add_translation"}


class EditPlan(Strict):
    """Revision Agent output: what to change and why, in the user's words."""

    ops: list[EditOp] = Field(default_factory=list, max_length=10)
    interpretation: str = Field(description="One line explaining what will change")
    unsupported: list[str] = Field(
        default_factory=list, description="Requests that no EditOp can express; surfaced to the user"
    )

    @property
    def needs_image_model(self) -> bool:
        return any(o.op in COSTLY_OPS for o in self.ops)

    @property
    def is_campaign_wide(self) -> bool:
        return any(o.op in CAMPAIGN_WIDE_OPS for o in self.ops)


def apply_ops(design: DesignDoc, ops: list[EditOp]) -> DesignDoc:
    """Apply design-scoped ops, returning a new version. Campaign-scoped ops are handled upstream."""
    data = design.model_dump()
    elements = {e["id"]: e for e in data["elements"]}
    for op in ops:
        match op.op:
            case "resize":
                el = _require(elements, op.element_id)
                el["overrides"]["scale"] = float(el["overrides"].get("scale", 1.0)) * op.scale
            case "move_slot":
                _require(elements, op.element_id)["slot"] = op.slot
            case "set_style":
                _require(elements, op.element_id)["style_token"] = op.style_token
            case "toggle_element":
                _require(elements, op.element_id)["visible"] = op.visible
            case "swap_photo":
                for el in elements.values():
                    if el["type"] == ElementType.AGENT_PHOTO:
                        el["asset_ref"] = f"profile.photos.{op.photo_id}"
            case "set_theme":
                data["theme"] = op.theme
            case "change_preset":
                data["canvas"] = Canvas.from_preset(op.preset).model_dump()
            case "regenerate_asset":
                _require(elements, op.element_id)["overrides"]["regenerate"] = True
            case _:
                continue  # campaign-wide ops (set_copy/set_fact/add_translation) applied by the workflow
    data["elements"] = list(elements.values())
    data["version"] = design.version + 1
    data["parent_version"] = design.version
    return DesignDoc.model_validate(data)


def _require(elements: dict[str, dict], element_id: str) -> dict:
    if element_id not in elements:
        raise KeyError(f"unknown element {element_id!r}; have {sorted(elements)}")
    return elements[element_id]


#: Which flat fields each operation needs, used when converting a model draft.
OP_FIELDS: dict[str, tuple[str, ...]] = {
    "set_copy": ("field", "text"),
    "set_fact": ("field", "value"),
    "resize": ("element_id", "scale"),
    "move_slot": ("element_id", "slot"),
    "set_style": ("element_id", "style_token"),
    "swap_photo": ("photo_id",),
    "add_translation": ("language", "placement"),
    "set_theme": ("theme",),
    "change_preset": ("preset",),
    "toggle_element": ("element_id", "visible"),
    "regenerate_asset": ("element_id", "guidance"),
}


def to_edit_ops(drafts: list) -> tuple[list[EditOp], list[str]]:
    """Convert flat model output into typed operations, reporting what could not be used."""
    ops: list[EditOp] = []
    rejected: list[str] = []
    for draft in drafts:
        data = draft.model_dump() if hasattr(draft, "model_dump") else dict(draft)
        op = data.get("op")
        wanted = OP_FIELDS.get(op)
        if wanted is None:
            rejected.append(f"unknown operation {op!r}")
            continue
        payload = {"op": op}
        for key in wanted:
            value = data.get(key)
            if value is not None:
                payload[key] = value
        try:
            ops.append(EditOpAdapter.validate_python(payload))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            rejected.append(f"{op}: {type(exc).__name__}")
    return ops, rejected
