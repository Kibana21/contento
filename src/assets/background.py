"""D4 — background imagery.

The image model produces *ingredients only*: mood, texture, festive scenes. It never draws
text, logos, the representative, or anything factual (ADR-001/002). Prompts are assembled
from AIA's photography brief (people-focused, candid, warm light, no single-use plastics),
so generated imagery matches the brand rather than generic stock.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..contracts.brand import BrandPack
from ..contracts.brief import CampaignBrief
from ..contracts.common import UsageRecord
from ..contracts.creative import CreativeDirection
from ..ai.model_gateway import ModelGateway

#: Never negotiable, whatever the creative brief says.
NEGATIVE = ("text, letters, words, numbers, captions, watermark, logo, brand mark, "
            "signage, distorted faces, deformed hands, plastic bottles, single-use plastic, "
            "collage, frame, border, ui elements")

STYLE = ("editorial photography, natural warm light, candid and authentic, "
         "shallow depth of field, generous negative space for text, "
         "muted background so foreground text stays legible")


@dataclass
class BackgroundResult:
    path: Path | None
    prompt: str
    model: str | None = None
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.path is not None


def build_prompt(direction: CreativeDirection, brief: CampaignBrief, brand: BrandPack) -> str:
    """Compose the image prompt from the direction plus AIA's photography rules."""
    parts = [direction.background_brief or f"a warm, uncluttered scene for a {brief.family.value} campaign"]
    if brief.festival:
        parts.append(f"{brief.festival.replace('_', ' ')} atmosphere, culturally respectful, Singapore")
    parts += [
        STYLE,
        f"colour palette led by AIA red {brand.red} with white space",
        "composition leaves the upper third and lower third clear for typography",
    ]
    return ". ".join(parts)


async def generate_background(
    gateway: ModelGateway,
    direction: CreativeDirection,
    brief: CampaignBrief,
    brand: BrandPack,
    out_dir: Path,
    *,
    aspect_ratio: str = "3:4",
    enabled: bool = True,
) -> BackgroundResult:
    """Generate one background image, or explain why it was skipped."""
    prompt = build_prompt(direction, brief, brand)
    if not enabled:
        return BackgroundResult(None, prompt, skipped_reason="image generation disabled")
    if not gateway.budget.can_spend(images=1):
        return BackgroundResult(None, prompt, skipped_reason="image budget exhausted")

    model_name = gateway.models["image"]
    full_prompt = f"{prompt}.\n\nDo not include: {NEGATIVE}."
    try:
        client = _genai_client()
        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config={"response_modalities": ["IMAGE"],
                    "image_config": {"aspect_ratio": aspect_ratio}},
        )
        data = _first_image_bytes(response)
        if data is None:
            return BackgroundResult(None, prompt, model_name, skipped_reason="model returned no image")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"background-{direction.id}.png"
        path.write_bytes(data)
        _crop_to_aspect(path, aspect_ratio)
    except Exception as exc:  # a missing image model must not fail the campaign
        return BackgroundResult(None, prompt, model_name, skipped_reason=f"{type(exc).__name__}: {exc}"[:200])

    gateway.usage_log.append(rec := UsageRecord(
        call_id=f"img-{direction.id}", node="background_generator", model=model_name,
        tier="image", images=1, campaign_id=gateway.campaign_id))
    gateway.budget.record(rec)
    return BackgroundResult(path, prompt, model_name)


def _crop_to_aspect(path: Path, aspect_ratio: str) -> None:
    """Trim the letterboxing some image models add, so the poster ground is edge to edge."""
    try:
        from PIL import Image

        w_ratio, h_ratio = (float(x) for x in aspect_ratio.split(":"))
    except Exception:
        return
    with Image.open(path) as im:
        im = im.convert("RGB")
        target = w_ratio / h_ratio
        width, height = im.size
        if abs(width / height - target) < 0.01:
            return
        if width / height > target:          # too wide: trim the sides
            new_w = int(height * target)
            box = ((width - new_w) // 2, 0, (width - new_w) // 2 + new_w, height)
        else:                                 # too tall: trim top and bottom
            new_h = int(width / target)
            box = (0, (height - new_h) // 2, width, (height - new_h) // 2 + new_h)
        im.crop(box).save(path)


def _first_image_bytes(response) -> bytes | None:
    for candidate in getattr(response, "candidates", None) or []:
        for part in getattr(candidate.content, "parts", None) or []:
            blob = getattr(part, "inline_data", None)
            if blob is not None and getattr(blob, "data", None):
                return blob.data
    return None


def _genai_client():
    import json

    from google import genai
    from google.oauth2 import service_account

    key_path = Path(os.environ.get("AIA_SERVICE_ACCOUNT", "api_key.json"))
    info = json.loads(key_path.read_text())
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return genai.Client(vertexai=True, project=info["project_id"],
                        location=os.environ.get("GEMINI_IMAGE_LOCATION", "global"),
                        credentials=creds)
