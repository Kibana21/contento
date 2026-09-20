"""Validation layers, in the order the pipeline runs them (ADR-006: rules first)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.brand import BrandPack
from ..contracts.common import ValidationReport
from ..contracts.design import DesignDoc
from .design import validate_design
from .dom import validate_dom
from ..contracts.design import ElementType
from .pixel import photo_rects, validate_pixels

__all__ = ["validate_design", "validate_dom", "validate_pixels", "validate_all"]


def validate_all(design: DesignDoc, geometry: dict[str, Any], image_path: Path,
                 brand: BrandPack) -> ValidationReport:
    theme = design.theme.value if hasattr(design.theme, "value") else str(design.theme)
    photo_ids = {e.id for e in design.elements
                 if e.type in {ElementType.AGENT_PHOTO, ElementType.IMAGE, ElementType.QR}}
    return (validate_design(design, brand)
            .merge(validate_dom(design, geometry, brand))
            .merge(validate_pixels(image_path, theme=theme,
                                   exclude=photo_rects(geometry, photo_ids))))
