# step-pmi-viewer

Read the PMI in a STEP file and write a self-contained web page showing it.

```bash
step-pmi-viewer part.step --open
```

One HTML file, no server. Dimensions with their tolerances, feature control
frames with ASME Y14.5 symbols and datum references, and datum feature symbols,
drawn on the part and legible at any zoom.

## Why

Viewing AP242 PMI has meant either a viewer that renders some of it, or NIST's
[STEP File Analyzer](https://github.com/usnistgov/SFA), which renders all of it
but is Windows-only because it reads STEP through the IFCsvr COM toolkit.

This reads the same data through OCCT and draws it in a browser.

## What it shows

| | |
| --- | --- |
| Dimensions | `Ø35`, `60°`, with `±0.15`, stacked `+0.05/-0.10`, or limits `35.2/34.8` |
| Geometric tolerances | `⌖ │ 0.75 │ A │ B │ C` — characteristic, zone, datum references |
| Datum features | boxed letters |

Annotation text is HTML, not geometry, so it stays crisp at any zoom, can be
selected, and costs nothing: a 60-annotation part is well under a megabyte.

In the page: orbit and zoom, toggle each kind of annotation, hide the far side,
make the part transparent, show edges, the bounding box, or the origin. Labels
declutter against each other in screen space as you move.

## Install

```bash
uv tool install step-pmi-viewer
```

`build123d` supplies the OCCT kernel through OCP; nothing else is needed.

## In the browser

`web/index.html` is the same reader running client side: Pyodide loads OCCT
compiled to WebAssembly, converts the STEP file you drop on the page, and shows
the page the CLI would have written. The file never leaves the tab.

```bash
uv build --wheel --out-dir web   # the page installs this wheel through micropip
python -m http.server -d web     # over http, so micropip can fetch it
```

A push to `main` builds that wheel again and publishes `web/` to GitHub Pages,
at <https://pzfreo.github.io/step-pmi-viewer/>.

The WebAssembly OCCT comes from [OCP.wasm](https://github.com/yeicor/OCP.wasm).
The first load pulls about 35 MB of Pyodide and OCCT and then caches it;
CTC-01 converts in a second or so, into a page identical byte for byte to the
one the CLI writes. Two pins at the top of the file belong together: the Pyodide
version, and the OCCT wheel, which stays on the 7.9 line because OCP 8 renames
the collection types the reader imports. Conversion runs on the main thread, so
a large part stops the tab while it is read.

## Two things OCCT gets wrong, worked around here

**Tolerance magnitudes read as zero.** `GetValue()` on a geometric tolerance
returns `0.0` for every tolerance in the NIST PMI reference files. The values are
in the STEP text as `LENGTH_MEASURE(0.75)`, but inside a complex entity its GD&T
reader does not unpack. The file is read a second time as text to recover them,
and a value OCCT does report is always preferred. See `magnitudes.py`.

**glTF export silently changes units.** A document read from STEP carries its
length unit, and `RWGltf_CafWriter` converts to metres — leaving the part a
thousandth the size of the annotation coordinates, and invisible. Setting the
converter's input and output units does not prevent it. The page instead fits
whatever geometry arrives onto the bounding box the annotations were computed
in, which is robust whatever the exporter does.

## Limits

* A dimension with no authored text position is skipped rather than drawn at the
  origin. In `nist_ctc_01_asme1_ap242-e1.stp` that is 13 of 21, all of them
  `linear distance` entries that do not appear as callouts on the drawing.
* Datum features are drawn as boxed letters, without the filled triangle a
  drawing puts on the leader.
* Saved views are read by OCCT but not yet offered as a view selector.
* Composite frames, "between" symbols and datum targets are not drawn.

## Licence

Apache-2.0.
