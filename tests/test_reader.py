"""Reading PMI out of a STEP file, checked against the published drawing.

The values asserted here are the ones printed on NIST's drawing for CTC-01,
`nist_ctc_01_asme1_rd.pdf`, so a change that silently alters what is read will
show up as a disagreement with the paper part.
"""

import pytest

from step_pmi_viewer import read_scene
from step_pmi_viewer.reader import NoGeometry


def test_scene_has_the_part(scene):
    assert scene.glb.startswith(b"glTF")
    assert scene.diagonal > 0


def test_counts_match_the_drawing(scene):
    assert scene.counts() == {"dimension": 8, "tolerance": 6, "datum": 3}


def test_every_diameter_on_the_drawing_is_read(scene):
    sizes = sorted(
        a.value for a in scene.annotations if a.group == "dimension" and a.cells[0].startswith("⌀")
    )
    assert sizes == [20.0, 20.0, 25.0, 35.0, 35.0, 35.0, 35.0]


def test_the_angular_dimension_is_read(scene):
    angles = [a for a in scene.annotations if a.cells[0].endswith("°")]
    assert [a.value for a in angles] == [60.0]
    assert angles[0].tolerance.upper == "±0.5"


def test_tolerances_are_written_as_the_drawing_writes_them(scene):
    shown = {a.cells[0]: a.tolerance for a in scene.annotations if a.group == "dimension"}
    styles = {t.style for t in shown.values() if t}
    assert styles == {"symmetric", "pair", "limits"}
    limits = [t for t in shown.values() if t and t.style == "limits"]
    assert limits and limits[0].upper == "35.2" and limits[0].lower == "34.8"


def test_feature_control_frames_match_the_drawing(scene):
    frames = {" ".join(a.cells) for a in scene.annotations if a.group == "tolerance"}
    assert frames == {
        "⌖ 0.75 A B C",  # position, twice
        "⌓ 1.25 A B C",  # profile of a surface
        "⌓ 0.5 A",
        "⟂ 1.5 A",  # perpendicularity
        "⏥ 0.2",  # flatness
    }


def test_tolerance_magnitudes_are_recovered(scene):
    """OCCT reports 0.0 for every one of these; they come from the STEP text."""
    values = sorted(a.value for a in scene.annotations if a.group == "tolerance")
    assert values == [0.2, 0.5, 0.75, 0.75, 1.25, 1.5]


def test_datums_are_read(scene):
    letters = sorted(a.cells[0] for a in scene.annotations if a.group == "datum")
    assert letters == ["A", "B", "C"]


def test_every_annotation_has_somewhere_to_be_drawn(scene):
    for a in scene.annotations:
        assert len(a.anchor) == 3 and len(a.origin) == 3


def test_a_file_without_geometry_is_reported(tmp_path):
    empty = tmp_path / "empty.step"
    empty.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
    with pytest.raises((NoGeometry, Exception)):
        read_scene(empty, tmp_path / "p.glb")


def test_saved_views_are_read(scene):
    """A saved view is the author's grouping of the PMI, as SFA presents it."""
    assert scene.views
    view = scene.views[0]
    assert view.name == "MBD_0"
    assert view.shows
    assert all(0 <= i < len(scene.annotations) for i in view.shows)
    assert view.direction is not None and view.up is not None


def test_a_view_only_names_annotations_we_drew(scene):
    """A view referring to something we skipped would filter to nothing."""
    for view in scene.views:
        assert view.shows, view.name


def test_topods_is_reached_through_the_name_either_build_has():
    """OCP.wasm binds TopoDS as a module of plain functions, desktop OCP as a
    class of _s statics. Naming either directly breaks the other."""
    from pathlib import Path

    from step_pmi_viewer import reader

    source = Path(reader.__file__).read_text()
    assert "TopoDS.Edge_s" not in source
    assert "TopoDS.Face_s" not in source
    assert "BRep_Tool.Triangulation_s" not in source
