"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
import tempfile
import webbrowser
from pathlib import Path

from . import __version__, recognise
from .page import write
from .reader import NoGeometry, read_scene


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="step-pmi-viewer",
        description="Read a STEP file's PMI and write a self-contained web page showing it.",
    )
    parser.add_argument("source", type=Path, nargs="?", help="input STEP file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output HTML file (default: <source stem>.html beside the input)",
    )
    parser.add_argument("--title", help="page title (default: the file's stem)")
    parser.add_argument(
        "--recognise",
        "--recognize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="when the file carries no PMI, show the features quid2pmi recognises in it "
        "instead of an empty page (default: do so when quid2pmi is installed)",
    )
    parser.add_argument("--open", action="store_true", help="open the page in a browser")
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    parser.add_argument("--version", action="version", version=f"step-pmi-viewer {__version__}")
    return parser


def _report(output: Path, counts: dict[str, int], origin: str, quiet: bool) -> None:
    if quiet:
        return
    total = sum(counts.values())
    size = output.stat().st_size / 1024
    what = origin or "annotations"
    print(f"{output}: {total} {what}, {size:.0f} kB", file=sys.stderr)
    for group, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {group:22s} {n}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.source is None:
        parser.print_usage(sys.stderr)
        print("step-pmi-viewer: an input STEP file is required", file=sys.stderr)
        return 2
    if not args.source.is_file():
        print(f"step-pmi-viewer: no such file: {args.source}", file=sys.stderr)
        return 2

    output = args.output or args.source.with_suffix(".html")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            scene = read_scene(args.source, Path(tmp) / "part.glb")
        # Nothing authored in the file: recognised features are the only thing
        # there is to show. They are a different claim, so the page says so.
        if not scene.annotations and not scene.graphics and args.recognise is not False:
            if recognise.available():
                counts = recognise.write_recognised(args.source, output)
                _report(output, counts, "recognised features", args.quiet)
                if args.open:
                    webbrowser.open(output.resolve().as_uri())
                return 0
            if args.recognise:
                raise recognise.Unavailable(
                    "recognising features needs quid2pmi: "
                    "pip install 'step-pmi-viewer[recognise]'"
                )
        write(scene, output, args.title)
    except NoGeometry as exc:
        print(f"step-pmi-viewer: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - surfaced verbatim
        print(f"step-pmi-viewer: {exc}", file=sys.stderr)
        return 1

    _report(output, scene.counts(), "", args.quiet)
    if args.open:
        webbrowser.open(output.resolve().as_uri())
    return 0
