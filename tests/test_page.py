"""Rendering a scene to one self-contained page."""

import base64
import json
import re

from step_pmi_viewer import render
from step_pmi_viewer.page import colour_for


def test_page_is_self_contained(scene):
    html = render(scene)
    assert html.lstrip().startswith("<!doctype html>")
    # Only three.js is fetched; the geometry and annotations are inlined.
    remote = set(re.findall(r'https?://[^"\')\s]+', html))
    assert all("jsdelivr" in url or "three" in url for url in remote), remote
    assert "__DATA__" not in html and "__COLOURS__" not in html


def test_geometry_is_embedded(scene):
    html = render(scene)
    blob = re.search(r'"glb":\s*"([A-Za-z0-9+/=]+)"', html)
    assert blob
    assert base64.b64decode(blob.group(1)).startswith(b"glTF")


def test_every_annotation_reaches_the_page(scene):
    html = render(scene)
    payload = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
    assert len(payload["labels"]) == len(scene.annotations)


def test_each_kind_has_a_colour(scene):
    html = render(scene)
    colours = json.loads(re.search(r"const GROUP_COLOUR = (\{.*?\});\n", html, re.S).group(1))
    for group in scene.counts():
        assert group in colours


def test_unknown_kinds_still_get_a_colour():
    assert colour_for("something-new").startswith("#")


def test_title_defaults_to_the_part_name(scene):
    assert scene.name in render(scene)
    assert "A Better Title" in render(scene, "A Better Title")


def test_a_caller_can_supply_its_own_palette(scene):
    import json
    import re

    html = render(scene, colours={"dimension": "#ff00ff", "holes": "#00ff00"})
    colours = json.loads(re.search(r"const GROUP_COLOUR = (\{.*?\});\n", html, re.S).group(1))
    assert colours["dimension"] == "#ff00ff"
    assert colours["holes"] == "#00ff00"
    assert colours["datum"] == "#2e8b57"


def test_label_detail_can_be_chosen(scene):
    """Full, minimal or none: a crowded part is unreadable at full detail."""
    html = render(scene)
    for level in ("full", "minimal", "none"):
        assert f'value="{level}"' in html
    # Minimal drops the descriptor, the tolerance and the datum compartments.
    assert 'body[data-detail="minimal"] .pmi .sub' in html
    assert 'body[data-detail="none"] .pmi-in { display: none; }' in html
