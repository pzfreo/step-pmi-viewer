"""ASME Y14.5 / ISO 1101 symbols, keyed by the names OCCT reports."""

from __future__ import annotations

#: Geometric characteristic symbols, by XCAFDimTolObjects tolerance type.
CHARACTERISTIC: dict[str, str] = {
    "Position": "⌖",
    "Flatness": "⏥",
    "Straightness": "—",
    "Circularity": "○",
    "Cylindricity": "⌭",
    "ProfileOfLine": "⌒",
    "ProfileOfSurface": "⌓",
    "Perpendicularity": "⟂",
    "Parallelism": "∥",
    "Angularity": "∠",
    "Concentricity": "◎",
    "Symmetry": "⌯",
    "CircularRunout": "↗",
    "TotalRunout": "↗",
}

#: Material condition modifiers, appended to a tolerance value.
MATERIAL: dict[str, str] = {
    "MaximumMaterialRequirement": "Ⓜ",
    "LeastMaterialRequirement": "Ⓛ",
    "RegardlessOfFeatureSize": "Ⓢ",
}

#: Prefixes a dimension value carries, by XCAF dimension type.
DIMENSION_PREFIX: dict[str, str] = {
    "Diameter": "⌀",
    "SphericalDiameter": "S⌀",
    "Radius": "R",
    "SphericalRadius": "SR",
}

DIAMETER = "⌀"
DEGREE = "°"
PLUS_MINUS = "±"


def characteristic(kind: str) -> str:
    """The drawing symbol for a tolerance kind, or the name if unknown."""
    return CHARACTERISTIC.get(kind, kind)


def dimension_text(kind: str, value: float) -> str:
    """A dimension value with its prefix, as a drawing writes it."""
    if kind in ("Angular", "Size_Angular"):
        return f"{value:g}{DEGREE}"
    return f"{DIMENSION_PREFIX.get(kind, '')}{value:g}"
