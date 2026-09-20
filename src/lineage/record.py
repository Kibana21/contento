"""D11 — lineage (BRD §30, FR-041/042, MVP acceptance 11).

Every exported asset must answer "how was this made?" without reconstructing the run:
which request, profile version, uploads, brand and compliance pack, template family,
models, findings, approvals and exports. The record is written as campaign.json and the
essentials are embedded in the image files themselves.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Strict, UsageRecord
from ..contracts.copy import Copy
from ..contracts.design import DesignDoc
from ..policy.rules import PolicyDecision

SCHEMA_VERSION = "0.1"


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


class ExportRecord(Strict):
    variation: str
    preset: str
    format: str
    path: str
    sha256_16: str
    width: int
    height: int


class VariationRecord(Strict):
    id: str
    direction: dict
    layout_family: str
    design_version: int
    design_path: str
    poster_path: str
    background: dict | None = None
    validation: dict
    auto_fixes: list[str] = Field(default_factory=list)
    reviewer_findings: list[dict] = Field(default_factory=list)


class LineageRecord(Strict):
    """The audit answer to 'how was this material produced?'"""

    schema_version: str = SCHEMA_VERSION
    campaign_id: str
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)
    user: str
    request_text: str
    request_sha256_16: str

    profile_id: str
    profile_version: str
    artifacts: list[dict] = Field(default_factory=list)

    brand_pack_version: str
    rules_version: str
    layout_families: list[str] = Field(default_factory=list)

    brief: dict
    policy: dict
    campaign_copy: dict = Field(description='The approved copy for this campaign')

    models: dict[str, str] = Field(default_factory=dict)
    usage: list[dict] = Field(default_factory=list)
    usage_summary: dict = Field(default_factory=dict)

    variations: list[VariationRecord] = Field(default_factory=list)
    exports: list[ExportRecord] = Field(default_factory=list)
    questions_asked: list[dict] = Field(default_factory=list)
    approvals: list[dict] = Field(default_factory=list)
    partial: bool = False
    notes: list[str] = Field(default_factory=list)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return path

    def stamp(self) -> dict[str, str]:
        """The short provenance embedded in every exported file."""
        return {
            "Software": "AIA Agent Marketing Studio",
            "CampaignID": self.campaign_id,
            "Created": self.created_at.isoformat(timespec="seconds"),
            "Agent": self.profile_id,
            "BrandPack": self.brand_pack_version,
            "CompliancePack": self.rules_version,
            "Risk": str(self.policy.get("risk", "")),
            "Models": ", ".join(f"{k}={v}" for k, v in self.models.items()),
            "LineageFile": "campaign.json",
        }


def build_record(
    *, campaign_id: str, user: str, request_text: str, brief: CampaignBrief,
    decision: PolicyDecision, copy: Copy, profile_version: str, brand_version: str,
    models: dict[str, str], usage: list[UsageRecord], usage_summary: dict,
    questions: list[dict], partial: bool = False,
) -> LineageRecord:
    return LineageRecord(
        campaign_id=campaign_id,
        user=user,
        request_text=request_text,
        request_sha256_16=hashlib.sha256(request_text.encode()).hexdigest()[:16],
        profile_id=brief.agent.profile_id,
        profile_version=profile_version,
        artifacts=[{"id": a.id, "uri": a.uri, "mime": a.mime, "intended_use": a.intended_use.value,
                    "facts": [f.field for f in a.extracted_facts]} for a in brief.artifacts],
        brand_pack_version=brand_version,
        rules_version=decision.rules_version,
        brief=brief.model_dump(mode="json"),
        policy=decision.model_dump(mode="json"),
        campaign_copy=copy.model_dump(mode="json"),
        models=models,
        usage=[u.model_dump(mode="json") for u in usage],
        usage_summary=usage_summary,
        questions_asked=questions,
        partial=partial,
    )


def embed_metadata(image_path: Path, stamp: dict[str, str]) -> None:
    """Write provenance into the exported file itself, so it survives being shared."""
    path = Path(image_path)
    try:
        if path.suffix.lower() == ".png":
            from PIL import Image, PngImagePlugin

            with Image.open(path) as im:
                info = PngImagePlugin.PngInfo()
                for key, value in stamp.items():
                    info.add_text(key, str(value))
                im.save(path, pnginfo=info)
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            from PIL import Image

            with Image.open(path) as im:
                comment = json.dumps(stamp, ensure_ascii=False).encode()
                im.save(path, quality=92, comment=comment)
    except Exception:  # metadata must never break an export
        return


def read_metadata(image_path: Path | str) -> dict[str, str]:
    from PIL import Image

    image_path = Path(image_path)
    with Image.open(image_path) as im:
        if image_path.suffix.lower() == ".png":
            return dict(im.info or {})
        comment = (im.info or {}).get("comment")
        return json.loads(comment) if comment else {}
