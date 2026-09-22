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


def test_repeats_can_be_grouped(scene):
    """A drawing points once at identical features and says how many."""
    html = render(scene)
    assert 'id="cbRepeat"' in html
    assert "repeatCount" in html
    # The echo keeps neither its text nor its leader.
    assert ".pmi.echo .pmi-in { visibility: hidden; }" in html
    assert "L.line.visible = false; L.dot.visible = false;" in html


def test_saved_views_reach_the_page(scene):
    import json
    import re

    html = render(scene)
    payload = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
    assert len(payload["views"]) == len(scene.views)
    if scene.views:
        assert 'name="view"' in html


def test_leaders_follow_the_label_text(scene):
    """With no label to point at, a leader points at nothing -- and over drawn
    PMI it doubles the author's own leaders."""
    html = render(scene)
    assert "function leadersWanted()" in html
    assert "const leaders = leadersWanted();" in html
    # Neither the far-side pass nor the repeat pass may switch them back on.
    assert "L.line.visible = leaders && !away && !L.stub;" in html
    assert "if (echo || !leaders)" in html


def test_the_cube_snaps_to_the_six_standard_views(scene):
    """The cube is only useful if every face maps to a direction to stand in."""
    html = render(scene)
    for face in ("RIGHT", "LEFT", "BACK", "FRONT", "TOP", "BOTTOM"):
        assert f"['{face}', [" in html
    # BoxGeometry's material order is +X, -X, +Y, -Y, +Z, -Z; the click uses it.
    assert "CUBE_FACES[hit.face.materialIndex][1]" in html


def test_the_part_centres_in_the_clear_area(scene):
    """The panel covers the right of the canvas, so centring on the window puts
    the part off to one side."""
    html = render(scene)
    assert "camera.setViewOffset(w, h, Math.min(PANEL_PX, w * 0.35) / 2, 0, w, h)" in html


def test_orbit_listens_where_pointer_events_arrive(scene):
    """The label overlay is pointer-events:none, so controls bound to it never
    see a drag on the part."""
    html = render(scene)
    assert "new OrbitControls(camera, stage)" in html
    assert "OrbitControls(camera, overlay" not in html


def test_dragging_on_the_cube_still_orbits(scene):
    """Swallowing the press would stop a drag on the cube turning the part."""
    html = render(scene)
    assert "event.stopPropagation()" not in html
    # The snap is decided on release, and only if the pointer stayed put.
    assert "addEventListener('pointerup'" in html
    assert "> 4) return;" in html


def test_zoom_controls_are_wired_up(scene):
    html = render(scene)
    for button in ("zoomIn", "zoomOut", "zoomFit"):
        assert f'id="{button}"' in html
        assert f"$('{button}').onclick" in html


def test_the_viewer_script_is_balanced(scene):
    """A stray brace leaves a blank page, which no other test would catch."""
    import re

    js = re.search(r'<script type="module">(.*?)</script>', render(scene), re.S).group(1)
    assert js.count("{") == js.count("}")
    assert js.count("(") == js.count(")")
    assert js.count("[") == js.count("]")


def test_the_panel_body_scrolls(scene):
    """A part with many families runs off a short window otherwise."""
    html = render(scene)
    assert "#panel .body { flex: 1; min-height: 0; overflow-y: auto;" in html
    # The title and the all/none footer sit outside it, so they stay put.
    assert html.index("<h1>") < html.index('<div class="body">') < html.index('<div id="foot">')


def test_drawn_pmi_has_one_control(scene):
    """It had two: a Display checkbox and the Show preset, which disagreed."""
    html = render(scene)
    assert "cbGraphic" not in html
    assert "graphicGroup.visible = drawnWanted();" in html


def test_a_leader_with_no_length_draws_nothing(scene):
    """It has no direction to point along, so the arrowhead would face anywhere."""
    html = render(scene)
    assert "const stub = tip.distanceTo(near) < d * 1e-4;" in html
    assert "L.line.visible = leaders && !away && !L.stub;" in html
    # Nor can such a label be judged to face away from the camera.
    assert "const away = !L.stub && cull &&" in html
