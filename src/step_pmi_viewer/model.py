"""What the viewer draws: one annotation, and the scene holding them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Vec = tuple[float, float, float]

#: How an annotation is drawn. A dimension is a value with an optional
#: tolerance; a feature control frame is a row of compartments; a datum feature
#: symbol is a boxed letter.
Kind = Literal["dimension", "frame", "datum"]


@dataclass(frozen=True)
class Tolerance:
    """A dimension's tolerance, in the form a drawing would show it."""

    style: Literal["symmetric", "pair", "limits"]
    #: ``±0.15`` for symmetric; the upper value or limit otherwise.
    upper: str
    #: The lower value or limit; unused when symmetric.
    lower: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"style": self.style, "upper": self.upper, "lower": self.lower}


@dataclass(frozen=True)
class Annotation:
    """One thing drawn beside the part."""

    kind: Kind
    #: Compartments of a frame, or the single text of a dimension or datum.
    cells: tuple[str, ...]
    #: The point on the part the leader lands on.
    anchor: Vec
    #: Where the text sits, a short way off the anchor.
    origin: Vec
    group: str = "dimension"
    detail: str = ""
    tolerance: Tolerance | None = None
    value: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "cells": list(self.cells),
            "anchor": list(self.anchor),
            "origin": list(self.origin),
            "group": self.group,
            "detail": self.detail,
            "tolerance": self.tolerance.to_dict() if self.tolerance else None,
            "value": self.value,
        }


@dataclass(frozen=True)
class Graphic:
    """Annotation geometry an author drew, rather than a value to write.

    AP242 carries most PMI twice: semantically, as a typed value this viewer can
    set in HTML, and graphically, as the line work a CAD system drew -- frames,
    leaders, and the glyphs of the text itself. A file may carry only the second,
    and then the drawn geometry is the annotation.
    """

    name: str
    group: str
    #: Line work -- frames, leaders, witness lines -- each a run of points.
    polylines: tuple[tuple[Vec, ...], ...] = ()
    #: Filled areas: the glyphs of the text, and arrowheads. Flat vertex
    #: coordinates and triangle indices into them.
    vertices: tuple[float, ...] = ()
    indices: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "group": self.group,
            "polylines": [[list(p) for p in line] for line in self.polylines],
            "vertices": list(self.vertices),
            "indices": list(self.indices),
        }


@dataclass(frozen=True)
class SavedView:
    """A named view of a subset of the PMI, as AP242 stores it.

    A part's annotations are rarely all meant to be read at once; a saved view
    is the author's grouping of them, together with where to stand to read them.
    """

    name: str
    #: Indices into ``Scene.annotations`` that this view shows.
    shows: tuple[int, ...]
    #: Where the camera looks from, and which way is up, when it exists.
    direction: Vec | None = None
    up: Vec | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "shows": list(self.shows),
            "direction": list(self.direction) if self.direction else None,
            "up": list(self.up) if self.up else None,
        }


@dataclass
class Scene:
    """A part, its bounding box, and everything annotated on it."""

    name: str
    glb: bytes
    bbox_min: Vec
    bbox_max: Vec
    annotations: list[Annotation] = field(default_factory=list)
    views: list[SavedView] = field(default_factory=list)
    graphics: list[Graphic] = field(default_factory=list)

    @property
    def diagonal(self) -> float:
        return sum((self.bbox_max[i] - self.bbox_min[i]) ** 2 for i in range(3)) ** 0.5

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.annotations:
            out[a.group] = out.get(a.group, 0) + 1
        return out
