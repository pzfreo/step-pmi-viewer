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
