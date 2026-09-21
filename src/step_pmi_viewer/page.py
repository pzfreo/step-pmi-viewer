"""Render a scene as one self-contained HTML page.

Everything is inlined -- the geometry as a base64 glTF, the annotations as JSON
-- so the result is a single file that opens from disk with no server. Only
three.js is fetched, from a CDN.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .model import Scene

TEMPLATE = Path(__file__).with_name("template.html")

#: Colour per annotation kind. Dimensions and tolerances follow the convention
#: drawings use, where size is one colour and geometric control another.
GROUP_COLOUR: dict[str, str] = {
    "dimension": "#2f6fb5",
    "tolerance": "#c0392b",
    "datum": "#2e8b57",
    "note": "#7d5ba6",
}
FALLBACK_COLOUR = "#55606b"


def colour_for(group: str) -> str:
    return GROUP_COLOUR.get(group, FALLBACK_COLOUR)


def render(scene: Scene, title: str | None = None) -> str:
    """The complete HTML page for ``scene``."""
    payload = {
        "part": scene.name,
        "bbox": {
            "min": list(scene.bbox_min),
            "max": list(scene.bbox_max),
            "diagonal": scene.diagonal,
        },
        "labels": [a.to_dict() for a in scene.annotations],
        "glb": base64.b64encode(scene.glb).decode(),
    }
    colours = dict(GROUP_COLOUR)
    for group in scene.counts():
        colours.setdefault(group, FALLBACK_COLOUR)

    return (
        TEMPLATE.read_text()
        .replace("__DATA__", json.dumps(payload))
        .replace("__COLOURS__", json.dumps(colours))
        .replace("__PART__", title or scene.name)
    )


def write(scene: Scene, destination: Path | str, title: str | None = None) -> Path:
    destination = Path(destination)
    destination.write_text(render(scene, title))
    return destination
