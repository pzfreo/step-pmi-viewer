"""Recognised features, for a STEP file that carries no PMI of its own.

Plenty of STEP files have no PMI at all -- anything exported from AP203, or from
a CAD system whose author never annotated the model. There is still something to
show: the features the geometry implies. quid2pmi recognises them with quiddity
and renders them through this same viewer.

It is an optional dependency, imported only when it is wanted, so the viewer
keeps working without it. The arrow between the packages points the other way --
quid2pmi depends on this one -- so the import stays inside the function that
needs it and nothing is imported at module load.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


class Unavailable(RuntimeError):
    """quid2pmi is not installed, so features cannot be recognised."""


def available() -> bool:
    """Whether recognition can be run in this environment."""
    from importlib.util import find_spec

    try:
        return find_spec("quid2pmi") is not None
    except (ImportError, ValueError):  # pragma: no cover - a broken install
        return False


def write_recognised(source: Path | str, destination: Path | str) -> dict[str, int]:
    """Recognise ``source``'s features and write the viewer page for them.

    Returns the count per feature family. The STEP file quid2pmi writes on the
    way is a by-product here and goes to a temporary directory.
    """
    try:
        from quid2pmi import convert  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on the environment
        # Name what is actually missing: quid2pmi itself may be present while one
        # of its dependencies is not, and "install quid2pmi" then reads as a lie.
        raise Unavailable(
            f"recognising features needs quid2pmi and its dependencies ({exc}): "
            "pip install 'step-pmi-viewer[recognise]'"
        ) from exc

    source, destination = Path(source), Path(destination)
    with tempfile.TemporaryDirectory() as tmp:
        report = convert(
            source, Path(tmp) / f"{source.stem}-pmi.step", viewer=destination, quiet=True
        )
    return dict(report.counts)
