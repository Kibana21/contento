"""Structured, repeating content — the thing a flat `Copy` cannot express.

`Copy` holds five scalar slots, which is enough for a poster with one headline and one body
paragraph. It has no way to say "four benefits, each an icon, a label and three lines" or
"five speakers, each with a role and a bio". That is why the reference brochures cannot be
built today: `EventDetails.speakers` is a list of bare strings the renderer never reads.

This is a sibling contract, not an extension of `Copy`, because the provenance differs.
`Copy` is words a model wrote. A speaker's bio and a product's benefit are **facts**, and they
must carry a source like any other fact (ADR-001). Merging the two would destroy exactly the
distinction the governance rests on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import Strict

ContentKind = Literal["benefit", "speaker", "chip", "step", "stat", "quote", "detail_row"]

#: `content.<kind>s.<index>.<field>` — the plural used in a reference, per kind.
PLURAL: dict[str, str] = {
    "benefit": "benefits", "speaker": "speakers", "chip": "chips", "step": "steps",
    "stat": "stats", "quote": "quotes", "detail_row": "detail_rows",
}
KIND_OF_PLURAL = {v: k for k, v in PLURAL.items()}


class ContentItem(Strict):
    """One row of a repeating module.

    `source` has no default on purpose: there is no code path that constructs an item without
    stating where its text came from. That is the structural guarantee that a bio is never
    invented, and it is the same idea as `Fact.source` on the brief.
    """

    id: str
    kind: ContentKind
    label: str | None = Field(default=None, max_length=80)
    role: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, max_length=400)
    value: str | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, description="A name from the icon catalogue")
    asset_ref: str | None = None
    source: str = Field(description="user | profile | artifact:<id> | derived")
    verbatim: bool = Field(default=False, description="Quoted from the source, not paraphrased")
    locked: bool = True

    @model_validator(mode="after")
    def _figures_must_be_quoted(self) -> ContentItem:
        """A fact-shaped figure has to be verbatim from its source.

        A paraphrased benefit is a style choice; a paraphrased figure is a misstatement.
        "Figure" is deliberately the *same* definition `facts.invented` already uses for copy —
        percentages, money, phone numbers, URLs, times and dates — rather than any digit. A
        bare numeral ("3 ways to plan") is not a claim, and inventing a second, stricter
        notion of a number here would surprise anyone who knows the copy rule.
        """
        if self.verbatim:
            return self
        from ..validate.copy import NUMERIC_PATTERNS  # deferred: validate imports contracts

        text = self.text()
        for kind, pattern in NUMERIC_PATTERNS.items():
            if match := pattern.search(text):
                raise ValueError(
                    f"content item {self.id!r} states a {kind} ({match.group()!r}) but is not "
                    "marked verbatim; figures must be quoted from an approved source"
                )
        return self

    def text(self) -> str:
        """Everything printable on this item, for the copy rules to scan."""
        return " ".join(t for t in (self.label, self.role, self.body, self.value) if t)

    def field(self, name: str) -> str | None:
        return {"label": self.label, "role": self.role, "body": self.body,
                "value": self.value, "icon": self.icon, "photo": self.asset_ref}.get(name)


class ContentSet(Strict):
    items: list[ContentItem] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def _unique_ids(self) -> ContentSet:
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate content item ids")
        return self

    def group(self, kind: str) -> list[ContentItem]:
        """Items of one kind, in order. Accepts the singular or the reference plural."""
        wanted = KIND_OF_PLURAL.get(kind, kind)
        return [i for i in self.items if i.kind == wanted]

    def resolve(self, key: str) -> str | None:
        """Resolve '<plural>.<index>.<field>', the tail of a `content.` reference.

        Raises KeyError with a useful message rather than returning a blank, because a silent
        empty string on a poster is worse than a loud failure.
        """
        try:
            plural, index, field = key.split(".", 2)
        except ValueError:
            raise KeyError(f"content reference {key!r} must be '<kind>.<index>.<field>'") from None
        if plural not in KIND_OF_PLURAL:
            raise KeyError(f"unknown content kind {plural!r}; have {sorted(KIND_OF_PLURAL)}")
        if not index.isdigit():
            raise KeyError(f"content index {index!r} is not a number")
        items = self.group(plural)
        position = int(index)
        if position >= len(items):
            raise KeyError(f"{plural}.{index} does not exist; there are {len(items)}")
        if field not in {"label", "role", "body", "value", "icon", "photo"}:
            raise KeyError(f"{field!r} is not an addressable content field")
        return items[position].field(field)

    def all_text(self) -> str:
        """Everything printable, for `validate_content` to scan in one pass."""
        return " ".join(i.text() for i in self.items)

    def counts(self) -> dict[str, int]:
        """How many of each kind — the Narrative Planner sizes pages from this."""
        out: dict[str, int] = {}
        for item in self.items:
            out[PLURAL[item.kind]] = out.get(PLURAL[item.kind], 0) + 1
        return out
