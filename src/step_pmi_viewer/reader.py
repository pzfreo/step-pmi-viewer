"""Read a STEP file's part geometry and its authored PMI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GProp import GProp_GProps
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.TColStd import TColStd_IndexedDataMapOfStringString
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import (
    XCAFDoc_Datum,
    XCAFDoc_Dimension,
    XCAFDoc_DocumentTool,
    XCAFDoc_GeomTolerance,
)

from .magnitudes import read_magnitudes
from .model import Annotation, Scene, Tolerance, Vec
from .symbols import MATERIAL, characteristic, dimension_text

#: How far off the anchor an annotation's text sits, as a share of the diagonal.
STANDOFF = 0.10


class NoGeometry(Exception):
    """The file carried no shape to draw."""


def _kind(enum_value: Any) -> str:
    return str(enum_value).split("_")[-1]


def _open(path: Path) -> TDocStd_Document:
    app = XCAFApp_Application.GetApplication_s()
    fmt = TCollection_ExtendedString("MDTV-XCAF")
    doc = TDocStd_Document(fmt)
    app.NewDocument(fmt, doc)
    reader = STEPCAFControl_Reader()
    for mode in ("SetGDTMode", "SetViewMode", "SetNameMode", "SetColorMode"):
        getattr(reader, mode)(True)
    reader.ReadFile(str(path))
    reader.Transfer(doc)
    return doc


def _to_glb(
    doc: TDocStd_Document,
    shapes: TDF_LabelSequence,
    tool: Any,
    deflection: float,
    destination: Path,
) -> bytes:
    for i in range(1, shapes.Length() + 1):
        BRepMesh_IncrementalMesh(tool.GetShape_s(shapes.Value(i)), deflection, False, 0.25, True)
    writer = RWGltf_CafWriter(TCollection_AsciiString(str(destination)), True)
    writer.Perform(doc, TColStd_IndexedDataMapOfStringString(), Message_ProgressRange())
    return destination.read_bytes()


def _surface_centre(shape: Any) -> Vec | None:
    if shape is None or shape.IsNull():
        return None
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, props)
    point = props.CentreOfMass()
    return (point.X(), point.Y(), point.Z())


def read_scene(path: Path | str, glb_path: Path | str) -> Scene:
    """Everything needed to draw a STEP file's part and its PMI."""
    path = Path(path)
    doc = _open(path)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    dimtol = XCAFDoc_DocumentTool.DimTolTool_s(doc.Main())

    shapes = TDF_LabelSequence()
    shape_tool.GetShapes(shapes)
    if shapes.Length() == 0:
        raise NoGeometry(f"{path} contains no shape")

    box = Bnd_Box()
    BRepBndLib.Add_s(shape_tool.GetShape_s(shapes.Value(1)), box)
    lo, hi = box.CornerMin(), box.CornerMax()
    bbox_min: Vec = (lo.X(), lo.Y(), lo.Z())
    bbox_max: Vec = (hi.X(), hi.Y(), hi.Z())
    diagonal = sum((bbox_max[i] - bbox_min[i]) ** 2 for i in range(3)) ** 0.5 or 1.0

    glb = _to_glb(doc, shapes, shape_tool, diagonal / 2000, Path(glb_path))
    scene = Scene(path.stem, glb, bbox_min, bbox_max)

    def anchor_for(label: Any) -> Vec | None:
        first, second = TDF_LabelSequence(), TDF_LabelSequence()
        if not dimtol.GetRefShapeLabel_s(label, first, second) or first.Length() == 0:
            return None
        return _surface_centre(shape_tool.GetShape_s(first.Value(1)))

    scene.annotations.extend(_dimensions(dimtol, anchor_for))
    scene.annotations.extend(_tolerances(dimtol, anchor_for, read_magnitudes(path), diagonal))
    scene.annotations.extend(_datums(dimtol))
    return scene


def _dimensions(dimtol: Any, anchor_for: Any) -> list[Annotation]:
    labels = TDF_LabelSequence()
    dimtol.GetDimensionLabels(labels)
    out: list[Annotation] = []
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        obj = XCAFDoc_Dimension.Set_s(label).GetObject()
        attach = obj.GetPointTextAttach()
        origin: Vec = (attach.X(), attach.Y(), attach.Z())
        # A dimension with no authored text position cannot be drawn anywhere
        # meaningful, and placing it at the origin would be worse than omitting.
        if origin == (0.0, 0.0, 0.0):
            continue
        kind = _kind(obj.GetType())
        name = obj.GetSemanticName()
        out.append(
            Annotation(
                kind="dimension",
                cells=(dimension_text(kind, obj.GetValue()),),
                anchor=anchor_for(label) or origin,
                origin=origin,
                group="dimension",
                detail=(name.ToCString() if name else "") or kind,
                tolerance=_tolerance_of(obj),
                value=obj.GetValue(),
            )
        )
    return out


def _tolerance_of(obj: Any) -> Tolerance | None:
    """A dimension's tolerance, written as a drawing writes it."""
    if obj.IsDimWithRange():
        return Tolerance("limits", f"{obj.GetUpperBound():g}", f"{obj.GetLowerBound():g}")
    upper, lower = obj.GetUpperTolValue(), obj.GetLowerTolValue()
    if not obj.IsDimWithPlusMinusTolerance() or not (upper or lower):
        return None
    if abs(upper - lower) < 1e-12:
        return Tolerance("symmetric", f"±{upper:g}")
    return Tolerance("pair", f"+{upper:g}", f"-{lower:g}")


def _tolerances(
    dimtol: Any, anchor_for: Any, magnitudes: dict[str, float], diagonal: float
) -> list[Annotation]:
    labels = TDF_LabelSequence()
    dimtol.GetGeomToleranceLabels(labels)
    out: list[Annotation] = []
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        obj = XCAFDoc_GeomTolerance.Set_s(label).GetObject()
        anchor = anchor_for(label)
        if anchor is None:
            continue
        kind = _kind(obj.GetType())
        name = obj.GetSemanticName()
        title = name.ToCString() if name else kind

        value = obj.GetValue()
        if value == 0.0 and title in magnitudes:
            value = magnitudes[title]
        zone = "⌀" if "Diameter" in _kind(obj.GetTypeOfValue()) else ""
        material = MATERIAL.get(_kind(obj.GetMaterialRequirementModifier()), "")

        out.append(
            Annotation(
                kind="frame",
                cells=(
                    characteristic(kind),
                    f"{zone}{value:g}{material}",
                    *_datum_letters(dimtol, label),
                ),
                anchor=anchor,
                origin=(anchor[0], anchor[1], anchor[2] + diagonal * STANDOFF),
                group="tolerance",
                detail=title,
                value=value,
            )
        )
    return out


def _datum_letters(dimtol: Any, tolerance_label: Any) -> tuple[str, ...]:
    """The datum references of a tolerance, in precedence order."""
    seq = TDF_LabelSequence()
    dimtol.GetDatumOfTolerLabels_s(tolerance_label, seq)
    letters: list[str] = []
    for i in range(1, seq.Length() + 1):
        name = XCAFDoc_Datum.Set_s(seq.Value(i)).GetObject().GetName()
        text = name.ToCString().strip() if name else ""
        if text and text not in letters:
            letters.append(text)
    return tuple(letters)


def _datums(dimtol: Any) -> list[Annotation]:
    labels = TDF_LabelSequence()
    dimtol.GetDatumLabels(labels)
    out: list[Annotation] = []
    seen: set[str] = set()
    for i in range(1, labels.Length() + 1):
        obj = XCAFDoc_Datum.Set_s(labels.Value(i)).GetObject()
        name = obj.GetName()
        letter = name.ToCString().strip() if name else ""
        attach = obj.GetPointTextAttach()
        origin: Vec = (attach.X(), attach.Y(), attach.Z())
        if not letter or letter in seen or origin == (0.0, 0.0, 0.0):
            continue
        seen.add(letter)
        out.append(
            Annotation(
                kind="datum",
                cells=(letter,),
                anchor=origin,
                origin=origin,
                group="datum",
                detail=f"Datum feature {letter}",
            )
        )
    return out
