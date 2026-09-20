"""D1 — load agent profiles, campaign requests and the brand pack from folders."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

import yaml

from .contracts.brand import BrandPack
from .contracts.brief import ArtifactRecord, IntendedUse
from .contracts.profile import AgentProfile, Photo, PhotoKind

REPO_ROOT = Path(__file__).resolve().parent.parent
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class LoaderError(RuntimeError):
    pass


# --------------------------------------------------------------------------- profile
def load_profile(profile_dir: Path | str) -> AgentProfile:
    """Read profiles/<id>/profile.yaml and discover photos/ and qr/ alongside it."""
    d = Path(profile_dir)
    yaml_path = d / "profile.yaml"
    if not yaml_path.exists():
        raise LoaderError(f"no profile.yaml in {d}")
    raw = yaml.safe_load(yaml_path.read_text()) or {}

    # flatten the human-friendly YAML shape into the contract
    contact = raw.pop("contact", {}) or {}
    data = {
        "id": raw.pop("id", d.name),
        "display_name": raw.pop("name", None) or raw.pop("display_name", d.name),
        "title": (raw.pop("title", "") or "").strip(),
        "agency": raw.pop("agency", None),
        "mobile": contact.get("mobile"),
        "email": contact.get("email"),
        "contact_url": contact.get("url"),
        "registration_url": raw.pop("registration_url", None),
        "qr_target": raw.pop("qr_target", None) or contact.get("url"),
        "languages": raw.pop("languages", None) or ["en"],
        "social_handles": raw.pop("social_handles", {}) or {},
        "version": str(raw.pop("version", "1")),
        "admin_approved": bool(raw.pop("admin_approved", False)),
        "credentials": raw.pop("credentials", []) or [],
        "preferences": _preferences(raw.pop("preferences", {}) or {}, raw.pop("preferred_photo", None)),
        "photos": _discover_photos(d, raw.pop("photos", None)),
    }
    return AgentProfile.model_validate(data)


def _preferences(prefs: dict, preferred_photo: str | None) -> dict:
    out = {"style": prefs.get("style", []) or [], "avoid": prefs.get("avoid", []) or []}
    pid = prefs.get("preferred_photo_id") or (Path(preferred_photo).stem if preferred_photo else None)
    if pid:
        out["preferred_photo_id"] = pid
    return out


def _discover_photos(profile_dir: Path, declared: list[dict] | None) -> list[dict]:
    if declared:
        return [{**p, "path": str(profile_dir / p["path"])} for p in declared]
    photos: list[dict] = []
    for f in sorted((profile_dir / "photos").glob("*")):
        if f.suffix.lower() not in PHOTO_SUFFIXES or f.stem.endswith("-cutout"):
            continue
        kind = f.stem if f.stem in {k.value for k in PhotoKind} else PhotoKind.PRIMARY.value
        cutout = f.with_name(f"{f.stem}-cutout.png")
        photos.append({"id": f.stem, "kind": kind, "path": str(f),
                       "cutout_path": str(cutout) if cutout.exists() else None,
                       "verified": True})
    return photos


# --------------------------------------------------------------------------- campaign
def load_request(campaign_dir: Path | str) -> tuple[str, list[ArtifactRecord]]:
    """Read campaigns/<name>/request.md and register the files in assets/ as artifacts."""
    d = Path(campaign_dir)
    req = d / "request.md"
    if not req.exists():
        raise LoaderError(f"no request.md in {d}")
    text = req.read_text().strip()
    if not text:
        raise LoaderError(f"{req} is empty")
    artifacts = [
        ArtifactRecord(
            id=f.stem,
            uri=str(f),
            mime=mimetypes.guess_type(f.name)[0] or "application/octet-stream",
            intended_use=IntendedUse.UNKNOWN,
        )
        for f in sorted((d / "assets").glob("*"))
        if f.is_file() and not f.name.startswith(".")
    ]
    return text, artifacts


# --------------------------------------------------------------------------- brand pack
def load_brand_pack(root: Path | str | None = None) -> BrandPack:
    """Load tokens, policy documents and approved assets from brand/aia-singapore/."""
    base = Path(root) if root else REPO_ROOT / "brand" / "aia-singapore"
    if not (base / "tokens").is_dir():
        raise LoaderError(f"brand pack not found at {base}")

    def tokens(name: str) -> dict:
        p = base / "tokens" / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else {}

    colour = tokens("colour")
    logo_tokens = tokens("logo")
    assets = base / "assets"
    logo_assets = {
        colour_name: path
        for colour_name, path in {
            "red": assets / "logos" / "corporate-logo-red.svg",
            "white": assets / "logos" / "corporate-logo-white.svg",
        }.items()
        if path.exists()
    }
    fonts = {
        style: path
        for style, path in {
            "display_regular": assets / "fonts" / "AIAEverest-Regular.woff2",
            "display_medium": assets / "fonts" / "AIAEverest-Medium.woff2",
            "body_regular": base / "fonts-open" / "OpenSans[wdth,wght].ttf",
            "zh_hans": base / "fonts-open" / "NotoSansSC[wght].ttf",
            "zh_hant": base / "fonts-open" / "NotoSansTC[wght].ttf",
            "ta": base / "fonts-open" / "NotoSansTamil[wdth,wght].ttf",
        }.items()
        if path.exists()
    }
    return BrandPack(
        root=base,
        version=str(colour.get("$schema_version", "0.2")),
        colour=colour,
        typography=tokens("typography"),
        spacing=tokens("spacing"),
        logo=logo_tokens,
        mountains=tokens("moving-mountains"),
        policies={p.stem: p for p in sorted((base / "policy").glob("*.md"))},
        fonts=fonts,
        logo_assets=logo_assets,
    )
