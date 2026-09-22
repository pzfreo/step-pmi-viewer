"""Read a STEP file's part geometry and its authored PMI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GProp import GProp_GProps
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.TCollection import TCollection_AsciiString as _AsciiString
from OCP.TColStd import TColStd_IndexedDataMapOfStringString
from OCP.TDF import TDF_LabelSequence, TDF_Tool
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import (
    XCAFDoc_Datum,
    XCAFDoc_Dimension,
    XCAFDoc_DocumentTool,
    XCAFDoc_GeomTolerance,
    XCAFDoc_View,
)

from .magnitudes import read_magnitudes
from .model import Annotation, Graphic, SavedView, Scene, Tolerance, Vec
from .symbols import MATERIAL, characteristic, dimension_text

#: How far off the anchor an annotation's text sits, as a share of the diagonal.
STANDOFF = 0.10


class NoGeometry(Exception):
    """The file carried no shape to draw."""


def _kind(enum_value: Any) -> str:
    return str(enum_value).split("_")[-1]


def _entry(label: Any) -> str:
    """A label's path in the document, used to match a view's references."""
    text = _AsciiString()
    TDF_Tool.Entry_s(label, text)
    return text.ToCString()


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


#: How finely a drawn curve is sampled, as a share of the part's diagonal. Fine
#: enough that glyph outlines read as letters, coarse enough to stay small.
GRAPHIC_DEFLECTION = 0.0006


def _static(owner: Any, name: str) -> Any:
    """A bound static, under whichever name the OCP build gives it.

    Desktop OCP binds ``TopoDS`` as a class whose statics carry an ``_s`` suffix.
    OCP.wasm binds it as a module of plain functions, so the page on GitHub Pages
    failed on the first file it was given with ``module 'OCP.TopoDS.TopoDS' has no
    attribute 'Edge_s'``. Every other static this module calls is reached before
    that point and so is known to resolve in both builds; these three are not.
    """
    return getattr(owner, f"{name}_s", None) or getattr(owner, name)


_as_edge = _static(TopoDS, "Edge")
_as_face = _static(TopoDS, "Face")
_triangulation = _static(BRep_Tool, "Triangulation")


def _polylines(shape: Any, deflection: float) -> tuple[tuple[Vec, ...], ...]:
    """The edges of a presentation shape, sampled into polylines."""
    lines: list[tuple[Vec, ...]] = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = _as_edge(explorer.Current())
        explorer.Next()
        try:
            curve = BRepAdaptor_Curve(edge)
            sampler = GCPnts_QuasiUniformDeflection(curve, deflection)
            if not sampler.IsDone() or sampler.NbPoints() < 2:
                continue
            points = [sampler.Value(i) for i in range(1, sampler.NbPoints() + 1)]
        except Exception:
            continue
        lines.append(tuple((p.X(), p.Y(), p.Z()) for p in points))
    return tuple(lines)


def _mesh(shape: Any) -> tuple[tuple[float, ...], tuple[int, ...]]:
    """The filled parts of a presentation: glyphs of the text, and arrowheads.

    These arrive already triangulated -- AP242 carries them as a triangulated
    surface set -- so they are read out rather than meshed. Drawing only the
    edges is why a viewer shows frames and leaders but no digits.
    """
    vertices: list[float] = []
    indices: list[int] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = _as_face(explorer.Current())
        explorer.Next()
        location = TopLoc_Location()
        triangulation = _triangulation(face, location)
        if triangulation is None:
            continue
        transform = location.Transformation()
        base = len(vertices) // 3
        for i in range(1, triangulation.NbNodes() + 1):
            point = triangulation.Node(i).Transformed(transform)
            vertices.extend((point.X(), point.Y(), point.Z()))
        for i in range(1, triangulation.NbTriangles() + 1):
            a, b, c = triangulation.Triangle(i).Get()
            indices.extend((base + a - 1, base + b - 1, base + c - 1))
    return tuple(vertices), tuple(indices)


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

    # Every shape, not just the first: a document whose first label carries no
    # geometry -- an assembly node, say -- leaves the box void and everything
    # downstream fails with "Bnd_Box is void".
    box = Bnd_Box()
    for i in range(1, shapes.Length() + 1):
        shape = shape_tool.GetShape_s(shapes.Value(i))
        if not shape.IsNull():
            BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        raise NoGeometry(f"{path} contains no shape with any extent")
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

    scene.annotations.extend(_dimensions(dimtol, anchor_for, diagonal))
    scene.annotations.extend(_tolerances(dimtol, anchor_for, read_magnitudes(path), diagonal))
    scene.annotations.extend(_datums(dimtol, anchor_for))
    scene.views.extend(_views(doc, scene))
    scene.graphics.extend(_graphics(dimtol, diagonal * GRAPHIC_DEFLECTION))
    return scene


def _graphics(dimtol: Any, deflection: float) -> list[Graphic]:
    """The drawn annotation geometry, for every annotation that carries any.

    Read for all of them, not only the ones with no semantic value: a file's
    author positioned and styled these, and they are what a CAD viewer shows.
    """
    from OCP.XCAFDoc import XCAFDoc_Datum as _Datum
    from OCP.XCAFDoc import XCAFDoc_Dimension as _Dimension
    from OCP.XCAFDoc import XCAFDoc_GeomTolerance as _Tolerance

    out: list[Graphic] = []
    for group, getter, attribute in (
        ("dimension", "GetDimensionLabels", _Dimension),
        ("tolerance", "GetGeomToleranceLabels", _Tolerance),
        ("datum", "GetDatumLabels", _Datum),
    ):
        labels = TDF_LabelSequence()
        getattr(dimtol, getter)(labels)
        for i in range(1, labels.Length() + 1):
            obj = attribute.Set_s(labels.Value(i)).GetObject()
            shape = obj.GetPresentation()
            if shape is None or shape.IsNull():
                continue
            lines = _polylines(shape, deflection)
            vertices, indices = _mesh(shape)
            if not lines and not indices:
                continue
            name = obj.GetPresentationName()
            out.append(
                Graphic(
                    name=(name.ToCString() if name else "") or group,
                    group=group,
                    polylines=lines,
                    vertices=vertices,
                    indices=indices,
                )
            )
    return out


def _views(doc: TDocStd_Document, scene: Scene) -> list[SavedView]:
    """The saved views, each naming the annotations it shows.

    A view refers to GD&T labels, so annotations carry the label path they came
    from and are matched back by it.
    """
    tool = XCAFDoc_DocumentTool.ViewTool_s(doc.Main())
    labels = TDF_LabelSequence()
    tool.GetViewLabels(labels)
    if labels.Length() == 0:
        return []

    where = {
        str(a.extra.get("entry")): i
        for i, a in enumerate(scene.annotations)
        if a.extra.get("entry")
    }

    out: list[SavedView] = []
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        referenced = TDF_LabelSequence()
        tool.GetRefGDTLabel(label, referenced)
        shows = tuple(
            sorted(
                where[entry]
                for k in range(1, referenced.Length() + 1)
                if (entry := _entry(referenced.Value(k))) in where
            )
        )
        if not shows:
            continue
        obj = XCAFDoc_View.Set_s(label).GetObject()
        name = obj.Name()
        direction = obj.ViewDirection()
        up = obj.UpDirection()
        out.append(
            SavedView(
                name=(name.ToCString() if name else f"View {i}") or f"View {i}",
                shows=shows,
                direction=(direction.X(), direction.Y(), direction.Z()),
                up=(up.X(), up.Y(), up.Z()),
            )
        )
    return out


#: Dimension kinds carrying no measured value. Their content is drawn glyphs
#: rather than a number, so there is nothing for this viewer to write as text.
PRESENTATION_ONLY = {"DimensionPresentation", "CommonLabel", "None"}


def _dimensions(dimtol: Any, anchor_for: Any, diagonal: float) -> list[Annotation]:
    labels = TDF_LabelSequence()
    dimtol.GetDimensionLabels(labels)
    out: list[Annotation] = []
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        obj = XCAFDoc_Dimension.Set_s(label).GetObject()
        kind = _kind(obj.GetType())
        attach = obj.GetPointTextAttach()
        authored: Vec = (attach.X(), attach.Y(), attach.Z())
        anchor: Vec | None = anchor_for(label)

        if authored != (0.0, 0.0, 0.0):
            origin: Vec = authored
        else:
            # No authored text position. A presentation-only kind has no value to
            # write either, so there is nothing to place; but a real dimension is
            # a callout the drawing shows, and its referenced geometry says where
            # the feature is even when the file does not say where its text went.
            if kind in PRESENTATION_ONLY or anchor is None:
                continue
            origin = (anchor[0], anchor[1], anchor[2] + diagonal * STANDOFF)

        name = obj.GetSemanticName()
        out.append(
            Annotation(
                kind="dimension",
                cells=(dimension_text(kind, obj.GetValue()),),
                anchor=anchor if anchor is not None else origin,
                origin=origin,
                group="dimension",
                detail=(name.ToCString() if name else "") or kind,
                tolerance=_tolerance_of(obj),
                value=obj.GetValue(),
                extra={"entry": _entry(label)},
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
                extra={"entry": _entry(label)},
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


def _datums(dimtol: Any, anchor_for: Any) -> list[Annotation]:
    """Datum feature symbols, each pointing at the surface it identifies.

    The attach point is where the letter sits, not what it names. Using it for
    both ends gives a leader of no length, and an arrowhead with no direction to
    face -- which is what the page drew before: a blob beside the symbol,
    touching nothing.
    """
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
                anchor=anchor_for(labels.Value(i)) or origin,
                origin=origin,
                group="datum",
                detail=f"Datum feature {letter}",
                extra={"entry": _entry(labels.Value(i))},
            )
        )
    return out
