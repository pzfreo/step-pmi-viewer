import os
from pathlib import Path

import pytest

#: The NIST PMI reference suite, which this package does not redistribute.
NIST = Path(os.environ.get("NIST_PMI_FILES", Path.home() / "steps/NIST-PMI-STEP-Files 2"))


def nist_file(name: str) -> Path:
    path = NIST / name
    if not path.is_file():
        pytest.skip(f"NIST PMI files not available at {NIST}")
    return path


@pytest.fixture(scope="session")
def ctc01() -> Path:
    """A part carrying 8 dimensions, 6 geometric tolerances and 3 datums."""
    return nist_file("nist_ctc_01_asme1_ap242-e1.stp")


@pytest.fixture(scope="session")
def scene(ctc01, tmp_path_factory):
    from step_pmi_viewer import read_scene

    return read_scene(ctc01, tmp_path_factory.mktemp("glb") / "p.glb")


@pytest.fixture(scope="session")
def no_pmi(tmp_path_factory) -> Path:
    """A plain solid: geometry, and no annotation of any kind.

    Built here rather than taken from the NIST set, which is all AP242 with PMI.
    A plate with a through hole and a chamfered edge is enough for recognition to
    have something to find.
    """
    from build123d import Box, Cylinder, Pos, export_step

    part = Box(40, 30, 10) - Pos(8, 0, 0) * Cylinder(4, 20)
    path = tmp_path_factory.mktemp("plain") / "plate.step"
    export_step(part, str(path))
    return path
