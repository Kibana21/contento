"""Resolve a DesignDoc into a concrete render context.

This is where `content_ref` values ("copy.headline", "facts.event.date") become text.
Facts come from the brief and profile only — never from the model that built the design.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.brand import BrandPack
from ..contracts.brief import CampaignBrief
from ..contracts.copy import Copy
from ..contracts.design import DesignDoc, Element, ElementType
from ..contracts.profile import AgentProfile
from ..policy.rules import PolicyDecision
from .mountains import mountains_svg
from .qr import qr_data_uri


class UnresolvedReference(KeyError):
    """A design references data that does not exist. Fails loudly rather than printing blanks."""


def _fmt(value: Any) -> str:
    if isinstance(value, dt.date):
        return value.strftime("%-d %B %Y")
    if isinstance(value, dt.time):
        return value.strftime("%-I.%M%p").lower().replace(":00", "")
    return "" if value is None else str(value)


@dataclass
class RenderContext:
    design: DesignDoc
    brief: CampaignBrief
    copy: Copy
    profile: AgentProfile
    brand: BrandPack
    decision: PolicyDecision | None = None
    assets_root: Path = field(default_factory=Path.cwd)

    # ---- data resolution --------------------------------------------------
    def facts(self) -> dict[str, Any]:
        """Every printable fact, profile first so verified contact data always wins."""
        data: dict[str, Any] = dict(self.profile.contact_facts())
        data |= {f.field if f.field.startswith(("event.", "cta.", "agent.")) else f.field: f.value
                 for f in self.brief.facts}
        if self.brief.event:
            for key, val in self.brief.event.model_dump().items():
                if val not in (None, [], ""):
                    data.setdefault(f"event.{key}", val)
        if self.brief.cta:
            data.setdefault("cta.text", self.brief.cta.text)
            data.setdefault("cta.url", self.brief.cta.url)
        return data

    def resolve(self, ref: str) -> str:
        namespace, _, key = ref.partition(".")
        if namespace == "copy":
            texts = self.copy.texts()
            if key not in texts:
                raise UnresolvedReference(f"copy slot {key!r} not produced by the copywriter")
            return texts[key]
        if namespace == "facts":
            facts = self.facts()
            if key not in facts:
                raise UnresolvedReference(f"fact {key!r} missing from brief/profile")
            return _fmt(facts[key])
        if namespace == "policy":
            from ..validate.copy import disclaimer_text

            if key != "disclaimer":
                raise UnresolvedReference(f"unknown policy reference {ref!r}")
            text = disclaimer_text(self.decision) if self.decision else None
            if not text:
                raise UnresolvedReference("no disclaimer required, but the design asks for one")
            return text
        if namespace == "profile":
            facts = self.profile.contact_facts()
            return _fmt(facts.get(f"agent.{key}", ""))
        raise UnresolvedReference(f"unknown reference namespace in {ref!r}")

    # ---- element rendering payloads --------------------------------------
    def element_payload(self, el: Element) -> dict[str, Any]:
        style = self.brand.type_scale().get(el.style_token or "", {})
        scale = float(el.overrides.get("scale", 1.0))
        payload: dict[str, Any] = {
            "id": el.id, "type": el.type.value, "slot": el.slot, "style": style,
            "scale": scale, "overrides": el.overrides, "text": None, "src": None, "svg": None,
        }
        match el.type:
            case ElementType.LOGO:
                payload["src"] = self._asset_uri(self.brand.logo_path(el.overrides.get("colour", "red")))
            case ElementType.AGENT_PHOTO:
                payload["src"] = self._photo_uri(el.asset_ref, shape=str(el.overrides.get("shape", "cutout")))
            case ElementType.QR:
                url = self._qr_target(el)
                payload["src"] = qr_data_uri(url, dark=self.brand.charcoal)
                payload["qr_target"] = url
            case ElementType.MOUNTAINS:
                # the SVG is generated at its container's size so it never overflows its box
                width = int(el.overrides.get("width", self.design.canvas.width))
                height = int(float(el.overrides.get("height", self.design.canvas.height * 0.42)) * scale)
                payload["svg"] = mountains_svg(
                    self.design.mountains.value, self.brand.mountains, self.brand.colour_hex,
                    on_red=str(getattr(self.design.theme, "value", self.design.theme)) == "bold",
                    shape_set=str(el.overrides.get("shape_set", "classic_3")),
                    width=width, height=height,
                    image_href=self._image_href(el),
                )
            case ElementType.IMAGE:
                payload["src"] = self._asset_uri(Path(el.asset_ref)) if el.asset_ref else None
            case ElementType.CONTACT_BLOCK:
                payload["lines"] = [v for k, v in self.profile.contact_facts().items()
                                    if k in {"agent.name", "agent.title", "agent.mobile", "agent.email"}]
            case _:
                payload["text"] = el.text if el.content_ref is None else self.resolve(el.content_ref)
        return payload

    # ---- helpers ----------------------------------------------------------
    def _asset_uri(self, path: Path) -> str:
        return Path(path).resolve().as_uri()

    def _photo_uri(self, asset_ref: str | None, *, shape: str = "cutout") -> str:
        """Cut-outs stand free; framed shapes sit on a brand-tinted panel, not studio grey."""
        photo_id = (asset_ref or "").split(".")[-1] if asset_ref else None
        photo = self.profile.photo(photo_id)
        if photo is None:
            raise UnresolvedReference(f"profile has no photo for {asset_ref!r}")
        cutout = Path(photo.cutout_path) if photo.cutout_path else None
        if cutout is None or not cutout.exists():
            return self._asset_uri(photo.path)
        if shape == "cutout":
            return self._asset_uri(cutout)
        from ..assets.portrait import framed

        tint = self.brand.colour_hex("core.red.20")
        white = self.brand.colour_hex("core.white")
        framed_path = framed(cutout, tint=tint, gradient_to=white,
                             ratio=1.0 if shape == "circle" else 0.78)
        return self._asset_uri(framed_path)

    def _qr_target(self, el: Element) -> str:
        url = (el.overrides.get("url") or (self.brief.cta.url if self.brief.cta else None)
               or self.profile.qr_target)
        if not url:
            raise UnresolvedReference("QR element has no verified URL")
        return str(url)

    def _image_href(self, el: Element) -> str | None:
        ref = el.overrides.get("image") or (self.design.background.asset
                                            if self.design.background.kind != "solid" else None)
        return self._asset_uri(Path(str(ref))) if ref else None

    def background_payload(self) -> dict[str, Any]:
        bg = self.design.background
        return {
            "kind": bg.kind,
            "src": self._asset_uri(Path(bg.asset)) if bg.asset else None,
            "colour": self.brand.colour_hex(bg.colour_token) if bg.colour_token else None,
        }
