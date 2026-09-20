"""Campaign copy — Copywriter output (BRD §19, Standalone §10)."""

from __future__ import annotations

from pydantic import Field

from .common import Strict


class Claim(Strict):
    """Any statement of fact about a product or benefit. Must cite an approved source."""

    text: str
    source_ref: str | None = None

    @property
    def is_grounded(self) -> bool:
        return bool(self.source_ref)


class Copy(Strict):
    headline: str = Field(max_length=120)
    subheadline: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=600)
    cta: str | None = Field(default=None, max_length=40)
    signature: str | None = None
    social_caption: str | None = Field(default=None, max_length=600)
    alt_text: str | None = Field(default=None, max_length=300)
    claims: list[Claim] = Field(default_factory=list)
    translations: dict[str, "Copy"] = Field(default_factory=dict)

    def texts(self) -> dict[str, str]:
        """Flat map of copy slots that the renderer may place."""
        out = {k: v for k, v in (("headline", self.headline), ("subheadline", self.subheadline),
                                 ("body", self.body), ("cta", self.cta), ("signature", self.signature))
               if isinstance(v, str) and v}
        for lang, tr in self.translations.items():
            out |= {f"{k}.{lang}": v for k, v in tr.texts().items()}
        return out


Copy.model_rebuild()
