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
