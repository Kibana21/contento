"""Agent (insurance representative) profile — BRD §12, Standalone §3."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from .common import Language, Strict


class PhotoKind(StrEnum):
    PRIMARY = "primary"
    FORMAL = "formal"
    CASUAL = "casual"
    CUTOUT = "cutout"


class Photo(Strict):
    id: str
    kind: PhotoKind
    path: Path
    cutout_path: Path | None = None
    verified: bool = False
    note: str | None = None


class Credential(Strict):
    text: str
    approved: bool = False
    expires: dt.date | None = None

    def is_usable(self, today: dt.date) -> bool:
        return self.approved and (self.expires is None or self.expires >= today)


class CreativePreferences(Strict):
    style: list[str] = Field(default_factory=list, description="e.g. premium, warm, minimal")
    avoid: list[str] = Field(default_factory=list)
    preferred_photo_id: str | None = None


class AgentProfile(Strict):
    """Verified identity data. The renderer takes contact facts from here, never from a model."""

    id: str
    display_name: str
    title: str = Field(description="Approved job title")
    agency: str | None = None
    mobile: str | None = None
    email: str | None = None
    contact_url: str | None = None
    registration_url: str | None = None
    languages: list[Language] = Field(default_factory=lambda: [Language.EN])
    photos: list[Photo] = Field(default_factory=list)
    qr_target: str | None = Field(default=None, description="URL the profile QR encodes")
    credentials: list[Credential] = Field(default_factory=list)
    preferences: CreativePreferences = Field(default_factory=CreativePreferences)
    social_handles: dict[str, str] = Field(default_factory=dict)
    version: str = "1"
    admin_approved: bool = False

    @field_validator("photos")
    @classmethod
    def _unique_photo_ids(cls, photos: list[Photo]) -> list[Photo]:
        ids = [p.id for p in photos]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate photo ids")
        return photos

    def photo(self, photo_id: str | None = None) -> Photo | None:
        """Resolve a photo id, falling back to the preferred, then primary, then first photo.

        A model may propose an id that does not exist; a poster with no portrait is worse
        than one using the representative's usual photo.
        """
        if photo_id:
            match = next((p for p in self.photos if p.id == photo_id), None)
            if match is not None:
                return match
        pref = self.preferences.preferred_photo_id
        if pref and pref != photo_id:
            match = next((p for p in self.photos if p.id == pref), None)
            if match is not None:
                return match
        return next((p for p in self.photos if p.kind == PhotoKind.PRIMARY),
                    self.photos[0] if self.photos else None)

    def contact_facts(self) -> dict[str, str]:
        """Fields the renderer may print. Only verified profile data."""
        out = {"agent.name": self.display_name, "agent.title": self.title}
        for key, val in (("agent.agency", self.agency), ("agent.mobile", self.mobile),
                         ("agent.email", self.email), ("agent.url", self.contact_url)):
            if val:
                out[key] = val
        return out
