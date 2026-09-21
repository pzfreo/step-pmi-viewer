"""Recover geometric tolerance magnitudes that OCCT's reader does not.

``XCAFDimTolObjects_GeomToleranceObject::GetValue`` returns 0.0 for every
tolerance in the NIST PMI reference files. The values are plainly in the STEP
text -- ``LENGTH_MEASURE(0.75)`` -- but held in a complex entity that OCCT's
GD&T reader does not unpack:

    #95=(
    LENGTH_MEASURE_WITH_UNIT()
    MEASURE_REPRESENTATION_ITEM()
    MEASURE_WITH_UNIT(LENGTH_MEASURE(0.75),#4361)
    REPRESENTATION_ITEM('')
    );

So the file is read a second time, as text, and a tolerance's magnitude is
looked up by the name OCCT also reports. This is a fallback: a value OCCT does
report is always preferred.
"""

from __future__ import annotations

import re
from pathlib import Path

#: A magnitude entity: the id, and the length it measures.
_MAGNITUDE = re.compile(
    r"#(\d+)=\([^)]*LENGTH_MEASURE_WITH_UNIT\(\)[^;]*?"
    r"MEASURE_WITH_UNIT\(LENGTH_MEASURE\(([-0-9.eE+]+)\)"
)
#: Both spellings: the general GEOMETRIC_TOLERANCE and specific subtypes such as
#: FLATNESS_TOLERANCE. Each names its magnitude as the third argument.
_TOLERANCE = re.compile(r"[A-Z_]*TOLERANCE\('([^']*)','[^']*',#(\d+)")


def read_magnitudes(path: Path | str) -> dict[str, float]:
    """Tolerance name to magnitude, read from the STEP text."""
    text = re.sub(r"\s*\n\s*", "", Path(path).read_text(errors="ignore"))
    measures = {eid: float(value) for eid, value in _MAGNITUDE.findall(text)}
    return {name: measures[ref] for name, ref in _TOLERANCE.findall(text) if ref in measures}
