"""Validation layers, in the order the pipeline runs them (ADR-006: rules first)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.brand import BrandPack
from ..contracts.common import ValidationReport
from ..contracts.design import DesignDoc
from .design import validate_design
from .dom import validate_dom
from .pixel import photo_rects, validate_pixels
from .spec import ElementSpec

__all__ = ["validate_design", "validate_dom", "validate_pixels", "validate_all",
           "validate_rendered", "ElementSpec"]


def validate_rendered(spec: ElementSpec, geometry: dict[str, Any], image_path: Path,
                      brand: BrandPack) -> ValidationReport:
    """The layers that read the rendered page. Shared by both engines."""
    return validate_dom(spec, geometry, brand).merge(
        validate_pixels(image_path, theme=spec.theme,
                        exclude=photo_rects(geometry, spec.masked_ids)))


def validate_all(design: DesignDoc, geometry: dict[str, Any], image_path: Path,
                 brand: BrandPack) -> ValidationReport:
    """Structured-engine entry point: the DesignDoc checks plus the rendered-page checks."""
    return validate_design(design, brand).merge(
        validate_rendered(ElementSpec.from_design(design), geometry, image_path, brand))
