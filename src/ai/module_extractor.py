"""Pulling repeating content out of an upload, without letting a model embellish it.

A speaker's bio and a product's benefit are *facts*. The Copywriter may not write them and
the Content Architect may not paraphrase them — they have to come from something the
representative actually supplied.

The division of labour: the model does the understanding (which part of a document is a
speaker, where one entry ends and the next begins), and code does the verifying (every string
it proposes must actually appear in the source). The model sees its rejections, so it can
correct itself rather than silently shipping an embellishment.

This is the structured counterpart of `facts.invented` in `validate/copy.py`, and it uses the
same definition of a figure, so the two rules cannot drift apart.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import Field

from ..contracts.common import Strict
from ..contracts.content import PLURAL, ContentItem, ContentSet

#: How much a proposal may be tidied before it stops being the source's words.
#: Case, whitespace and surrounding punctuation only — never word order, never new words.
_TIDY = re.compile(r"[\s ]+")
_STRIPPABLE = " \t\n\r.,;:—–-•·\"'()[]"


class ProposedItem(Strict):
    """What the model offers. Nothing here is trusted until it is verified."""

    label: str | None = Field(default=None, max_length=80)
    role: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, max_length=400)
    value: str | None = Field(default=None, max_length=40)
    icon: str | None = Field(default=None, max_length=40)

    def strings(self) -> dict[str, str]:
        return {k: v for k, v in (("label", self.label), ("role", self.role),
                                  ("body", self.body), ("value", self.value)) if v}


def normalise(text: str) -> str:
    """Fold to a comparable form: NFKC, collapsed whitespace, casefolded.

    NFKC matters because a PDF may carry typographic quotes and ligatures that a model
    helpfully retypes as ASCII; that is transcription, not invention.
    """
    folded = unicodedata.normalize("NFKC", text)
    return _TIDY.sub(" ", folded).strip(_STRIPPABLE).casefold()


def is_sourced(claim: str, source: str) -> bool:
    """Is this string actually in the document, allowing only cosmetic tidying?"""
    needle = normalise(claim)
    return bool(needle) and needle in normalise(source)


def verify(proposal: ProposedItem, source: str) -> list[str]:
    """Which fields of a proposal are not in the source. Empty means it is usable."""
    return [name for name, value in proposal.strings().items() if not is_sourced(value, source)]


def build_items(proposals: list[ProposedItem], kind: str, source_text: str, artifact_id: str,
                *, start: int = 0) -> tuple[list[ContentItem], list[str]]:
    """Turn verified proposals into locked content items, and report what was rejected.

    Everything accepted is stamped `verbatim=True`, because that is exactly what was
    checked. An item that carries a figure would otherwise be refused by `ContentItem`.
    """
    accepted: list[ContentItem] = []
    rejected: list[str] = []
    for offset, proposal in enumerate(proposals):
        missing = verify(proposal, source_text)
        if missing:
            shown = ", ".join(f"{f}={proposal.strings()[f][:40]!r}" for f in missing)
            rejected.append(f"not found in the document: {shown}")
            continue
        if not proposal.strings():
            rejected.append("proposal had no text")
            continue
        accepted.append(ContentItem(
            id=f"{kind}-{start + offset}",
            kind=kind,                      # type: ignore[arg-type]
            label=proposal.label,
            role=proposal.role,
            body=proposal.body,
            value=proposal.value,
            icon=proposal.icon,
            source=f"artifact:{artifact_id}",
            verbatim=True,
        ))
    return accepted, rejected


def merge(existing: ContentSet, new: list[ContentItem]) -> ContentSet:
    """Append, skipping anything already present under the same id."""
    seen = {item.id for item in existing.items}
    return ContentSet(items=[*existing.items, *(i for i in new if i.id not in seen)])


def summarise(kind: str, accepted: list[ContentItem], rejected: list[str]) -> dict:
    """What the model is told. Rejections are explicit so it can correct itself."""
    return {
        "kind": PLURAL.get(kind, kind),
        "accepted": [{"id": i.id, "label": i.label, "role": i.role} for i in accepted],
        "rejected": rejected,
        "note": ("Every accepted item is quoted from the document and locked. Rejected items "
                 "were not found in it — quote the wording exactly, or leave them out. "
                 "Never write a bio or a benefit from memory."),
    }
