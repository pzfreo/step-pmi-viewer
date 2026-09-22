"""The browser viewer, whose Python is the same Python the CLI runs.

`web/index.html` carries a short script that Pyodide executes. It is tested
here against a native interpreter: what it asks of the package is what the
page gets, so a rename that breaks the page fails the suite rather than the
browser.
"""

import json
import re
from pathlib import Path

import pytest

from step_pmi_viewer import __version__

PAGE = Path(__file__).resolve().parents[1] / "web" / "index.html"


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text()


def test_the_page_installs_this_version(page):
    wheel = re.search(r'const PACKAGE = "(.*?)"', page).group(1)
    assert wheel == f"./step_pmi_viewer-{__version__}-py3-none-any.whl"


def test_the_glue_converts_a_step_file(page, ctc01):
    glue = re.search(r"const GLUE = `(.*?)`;", page, re.S).group(1)
    scope: dict = {}
    exec(glue, scope)
    result = json.loads(scope["convert"](ctc01.name, ctc01.read_bytes()))
    assert result["name"] == ctc01.stem
    assert result["counts"] == {"dimension": 8, "tolerance": 6, "datum": 3}
    assert result["html"].lstrip().startswith("<!doctype html>")


def test_both_routes_produce_the_same_page(page, ctc01, tmp_path):
    """The CLI and the browser must not drift apart.

    Both call read_scene then render, so the page a reader gets should not
    depend on which one produced it. Asserting that here means a change made
    for one route cannot quietly diverge the other.
    """
    from step_pmi_viewer import read_scene, render

    glue = re.search(r"const GLUE = `(.*?)`;", page, re.S).group(1)
    scope: dict = {}
    exec(glue, scope)
    in_browser = json.loads(scope["convert"](ctc01.name, ctc01.read_bytes()))["html"]

    scene = read_scene(ctc01, tmp_path / "part.glb")
    locally = render(scene)

    # The glTF is re-meshed per call and floating point need not repeat exactly,
    # so compare the annotations and the page around them rather than the bytes.
    def without_geometry(html: str) -> str:
        return re.sub(r'"glb":\s*"[A-Za-z0-9+/=]*"', '"glb":""', html)

    assert without_geometry(in_browser) == without_geometry(locally)


def test_the_package_wheel_is_fetched_past_the_cache():
    """Its filename never changes, so a browser that has seen one version will
    reuse it and a fix never reaches the page."""
    page = (Path(__file__).parents[1] / "web" / "index.html").read_text()
    assert 'fetch(PACKAGE, { cache: "reload" })' in page


def test_the_glue_recognises_a_file_with_no_pmi(page, no_pmi):
    """The browser's recognition path is the same code the CLI runs."""
    from step_pmi_viewer import recognise

    if not recognise.available():
        pytest.skip("quid2pmi is not installed")

    glue = re.search(r"const GLUE = `(.*?)`;", page, re.S).group(1)
    scope: dict = {}
    exec(glue, scope)
    result = json.loads(scope["recognise"](no_pmi.name, no_pmi.read_bytes()))
    assert sum(result["counts"].values()) > 0
    assert '"origin": "recognised features"' in result["html"]


def test_the_recogniser_wheel_matches_what_ci_builds(page):
    wheel = re.search(r'const RECOGNISER = "(.*?)"', page).group(1)
    workflow = (PAGE.parents[1] / ".github" / "workflows" / "pages.yml").read_text()
    assert "uv build --wheel .quid2pmi --out-dir web" in workflow
    assert wheel.startswith("./quid2pmi-") and wheel.endswith("-py3-none-any.whl")


def test_the_unbuildable_packages_are_stood_in_for(page):
    """lib3mf and psutil have no wasm wheel anywhere and build123d imports both
    at load; OCP is already present under the name OCP.wasm publishes."""
    standins = re.search(r"const STANDINS = `(.*?)`;", page, re.S).group(1)
    for name in ("cadquery-ocp-novtk", "lib3mf", "psutil"):
        assert f'add_mock_package("{name}"' in standins
    # build123d 0.12 wants an OCP 8 that OCP.wasm does not build.
    assert 'micropip.install("build123d<0.12")' in page
