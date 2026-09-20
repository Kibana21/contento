"""Brand pack — versioned, machine-readable AIA rules and assets (BRD §13, ADR-002)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from .common import Strict


class BrandPack(Strict):
    """Loaded from brand/<market>/. Tokens are data; policies are reviewer rubrics."""

    market: str = "aia-singapore"
    version: str = "0.2"
    root: Path
    colour: dict[str, Any] = Field(default_factory=dict)
    typography: dict[str, Any] = Field(default_factory=dict)
    spacing: dict[str, Any] = Field(default_factory=dict)
    logo: dict[str, Any] = Field(default_factory=dict)
    mountains: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Path] = Field(default_factory=dict)
    fonts: dict[str, Path] = Field(default_factory=dict)
    logo_assets: dict[str, Path] = Field(default_factory=dict)

    # ---- colour -----------------------------------------------------------
    def colour_hex(self, token: str) -> str:
        """Resolve 'core.red', 'core.red.60', 'secondary.blue' or 'secondary.blue.40' to a hex value."""
        parts = token.split(".")
        node: Any = self.colour
        if parts[0] == "core":
            node = self.colour["core"][parts[1]]
            if len(parts) == 2:
                return node["value"] if isinstance(node, dict) else node
            return node["tints"][parts[2]]
        if parts[0] == "secondary":
            node = self.colour["secondary"][parts[1]]
            return node["value"] if len(parts) == 2 else node["tints"][parts[2]]
        raise KeyError(f"unknown colour token {token!r}")

    @property
    def red(self) -> str:
        return self.colour_hex("core.red")

    @property
    def charcoal(self) -> str:
        return self.colour_hex("core.charcoal")

    # ---- rules used by validators ----------------------------------------
    def rule(self, name: str) -> Any:
        return self.colour.get("rules", {}).get(name)

    @property
    def max_secondary_colours(self) -> int:
        return int(self.rule("max_secondary_colours")["value"])

    @property
    def min_text_contrast(self) -> float:
        return float(self.rule("min_text_contrast")["value"])

    @property
    def allowed_logo_positions(self) -> list[str]:
        return list(self.logo.get("allowed_positions", []))

    def logo_path(self, colour: str = "red") -> Path:
        try:
            return self.logo_assets[colour]
        except KeyError as exc:
            raise KeyError(f"no {colour} logo asset; have {sorted(self.logo_assets)}") from exc

    def font_path(self, style: str) -> Path | None:
        return self.fonts.get(style)

    def type_scale(self) -> dict[str, Any]:
        return self.typography["poster_scale"]["styles"]

    def hierarchy(self) -> dict[str, Any]:
        return self.typography["hierarchy"]
