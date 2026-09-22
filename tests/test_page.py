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
    the part off to one side -- except on a narrow screen, where the panel slides
    off the model instead of sitting beside it and covers nothing until asked for."""
    html = render(scene)
    assert "camera.setViewOffset(w, h, panelRoom() / 2, 0, w, h)" in html
    assert "innerWidth <= 640 ? 0 : Math.min(PANEL_PX, innerWidth * 0.35)" in html


def test_the_part_turns_past_the_poles(scene):
    """OrbitControls keeps up up, which costs the part its roll: the polar angle
    stops dead at top and bottom, so a drag meaning "keep turning it over" hits a
    wall halfway round. Its pan and zoom are kept; only the rotation is ours."""
    html = render(scene)
    assert "controls.enableRotate = false;" in html
    # The camera's own axes turn it, and its up is carried round with them --
    # which is the whole difference from an orbit.
    assert "tumbleAxis.setFromMatrixColumn(camera.matrix, 1)" in html
    assert "tumbleAxis.setFromMatrixColumn(camera.matrix, 0)" in html
    assert "camera.up.applyQuaternion(tumbleQ);" in html
    # A pinch is OrbitControls' to deal with. The first finger is still the
    # primary one, and left alone it would spin the part while the other two
    # were only trying to zoom it.
    assert "if (touching.size > 1) { tumbling = null; return; }" in html


def test_the_cube_offers_its_edges_and_corners(scene):
    """Six faces cannot express a three-quarter view, which is how a part is
    usually read -- and is what the page itself opens at."""
    html = render(scene)
    assert "v => (Math.abs(v) > CUBE_EDGE_BAND ? Math.sign(v) : 0)" in html
    # A corner arrives as [1, 1, 1], root-three long; taken as given it would
    # stand the camera that much further off.
    assert "const heading = new THREE.Vector3(...direction).normalize();" in html
    assert 'id="zoomHome"' in html


def test_the_part_is_framed_by_its_own_corners(scene):
    """The old standoff was the largest side of the box times a fudge factor,
    which is a guess at this and a loose one: it left the part at barely half the
    window, and a third of the width of a phone held upright."""
    html = render(scene)
    assert "function standoff(heading, up)" in html
    assert "halfAcross = Math.max(halfAcross, Math.abs(at.dot(across)));" in html
    # The panel covers the right of the canvas, so the width to fit into is the
    # strip it leaves clear, not the whole window.
    assert "const clear = Math.max(innerWidth - panelRoom(), 1);" in html
    # And the opening view is that same framing, once the window's shape is known.
    assert "home(true);" in html


def test_the_view_rolls_a_quarter_turn_at_a_time(scene):
    """Square onto a face nothing else turns the part in the plane of the screen:
    an orbit takes the long way round and a tumble cannot do it at all, since both
    move where you stand rather than which way up you are standing."""
    html = render(scene)
    for button in ("rollLeft", "rollRight"):
        assert f'id="{button}"' in html
        assert f"$('{button}').onclick" in html
    assert ".applyAxisAngle(heading, (quarters * Math.PI) / 2);" in html


def test_the_nearest_of_two_equals_does_not_change_its_mind(scene):
    """OrbitControls.update() takes the camera out to spherical coordinates and
    back every frame, and that round trip is not the identity in floating point:
    left alone the camera random-walks by an ulp a frame. Two identical features
    either side of a part seen square-on sit at the same depth to well within
    that, so raw depth let the walk decide which of them spoke for the pair."""
    html = render(scene)
    ordering = "Math.round(a.depth * RESOLVED) - Math.round(b.depth * RESOLVED) || a.L.at - b.L.at"
    assert ordering in html
    # The tie-break is where the label came in the file, which cannot wobble.
    assert "at: placedLabels.length," in html


def test_which_side_a_feature_is_on_is_settled_once_per_move(scene):
    """Asked every frame, it is asked all the way through a turn as well, and a
    label whose feature passes the threshold on the way winks out and back before
    the view has arrived -- a flicker, with a hand nowhere near anything."""
    html = render(scene)
    assert "if (flight === null) {" in html
    assert "const away = L.away;" in html


def test_the_cube_lights_up_under_the_pointer(scene):
    """Six flat faces say nothing about the rim between them being pickable, so
    the edges and corners were a secret worth keeping from nobody."""
    html = render(scene)
    assert "cube.add(highlight);" in html
    # Shaped from the same direction a press there would return: a square in a
    # face, a strip along an edge, a nub at a corner.
    assert "const size = out ? (1.02 - CUBE_EDGE_BAND) * HALF : 2 * CUBE_EDGE_BAND * HALF;" in html
    assert "markCube(tumbling ? null : faceAt(event.clientX, event.clientY));" in html


def test_the_view_turns_to_a_snap_rather_than_cutting(scene):
    """A cut loses the reader: with nothing moving in between there is no telling
    which way the part turned, only that it is showing a different side."""
    html = render(scene)
    assert "advanceFlight();" in html
    # Orientation goes across as a quaternion. Going home from upside down flips
    # up end for end, and a vector interpolated through that passes through zero.
    assert "camera.quaternion.slerpQuaternions(" in html
    # And a hand on the part outranks a flight still in the middle of itself.
    assert "flight = null;\n  tumbling = {" in html


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
    assert "const stub = tip.distanceTo(path[path.length - 2]) < d * 1e-4;" in html
    assert "L.line.visible = leaders && !away && !L.stub;" in html
    # Nor can such a label be judged to face away from the camera -- though the
    # part can still be in front of it, which is tested separately.
    assert "(!L.stub &&" in html


def test_a_leader_follows_the_bends_it_is_given(scene):
    """A recognised feature bends its leader so the last leg leaves the surface
    along the normal; an authored one gives no bends and draws straight."""
    html = render(scene)
    assert "const path = [near, ...(a.via || []).map(v => new THREE.Vector3(...v)), tip];" in html
    assert "geom.setPositions(path.flatMap(p => [p.x, p.y, p.z]));" in html
    # The arrowhead faces along the final leg, not along the whole leader.
    assert "tip.clone().sub(path[path.length - 2]).normalize()" in html


def test_the_far_side_cull_keeps_what_is_edge_on(scene):
    """At 0.12 it hid everything within a few degrees of edge-on, which on a
    round part is most of what you are looking at."""
    html = render(scene)
    assert ".dot(L.out) < -0.25));" in html


def test_a_label_is_hidden_when_the_part_is_in_the_way(scene):
    """Facing away from the camera is a proxy for being behind the part, and on
    anything but a convex lump it is wrong both ways."""
    html = render(scene)
    assert "function testOcclusion()" in html
    assert "L.buried = occluder.intersectObjects(meshes, false).length > 0;" in html
    # Casting a ray per label is too slow every frame, so it waits for the view
    # to settle -- and runs again when the part is hidden or made see-through.
    assert "} else if (still >= 0 && ++still === 6) {" in html
    assert "const solid = $('cbPart').checked && Number($('alpha').value) === 0;" in html


def test_the_part_opens_see_through_with_its_edges(scene):
    """A recognised part is mostly interior -- pockets, bores and channels are
    the features, and an opaque solid shows none of them."""
    html = render(scene)
    assert '<input type="range" id="alpha" min="0" max="90" value="85">' in html
    assert '<input type="checkbox" id="cbEdges" checked>' in html


def test_the_occlusion_state_is_declared_before_it_is_used(scene):
    """applyLook resets it and runs during setup. Declared further down, it is
    in its temporal dead zone then, and reading it throws before the render loop
    starts: a blank page with a working panel beside it, which no other test
    here would notice."""
    html = render(scene)
    for name in ("const occluder", "let still", "const lastEye"):
        assert html.index(name) < html.index("function applyLook"), name
