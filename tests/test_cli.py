"""The command line wrapper."""

import pytest

from step_pmi_viewer.cli import main


def test_writes_a_page_beside_the_input(ctc01, tmp_path, capsys):
    source = tmp_path / "part.step"
    source.write_bytes(ctc01.read_bytes())
    assert main([str(source), "-q"]) == 0
    assert (tmp_path / "part.html").is_file()
    assert capsys.readouterr().err == ""


def test_reports_what_it_found(ctc01, tmp_path, capsys):
    assert main([str(ctc01), "-o", str(tmp_path / "o.html")]) == 0
    err = capsys.readouterr().err
    assert "annotations" in err and "tolerance" in err


def test_missing_file_is_reported(tmp_path, capsys):
    assert main([str(tmp_path / "absent.step")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_no_argument_is_reported(capsys):
    assert main([]) == 2
    assert "required" in capsys.readouterr().err


def test_a_file_with_no_pmi_falls_back_to_recognised_features(no_pmi, tmp_path, capsys):
    """An AP203 export carries no annotation at all. The features the geometry
    implies are the only thing there is to show."""
    from step_pmi_viewer import recognise

    if not recognise.available():
        pytest.skip("quid2pmi is not installed")

    out = tmp_path / "recognised.html"
    assert main([str(no_pmi), "-o", str(out)]) == 0
    assert "recognised features" in capsys.readouterr().err
    # The page says so too, so it cannot be read as the author's own PMI.
    assert '"origin": "recognised features"' in out.read_text()


def test_no_recognise_leaves_the_file_speaking_for_itself(no_pmi, tmp_path, capsys):
    out = tmp_path / "bare.html"
    assert main([str(no_pmi), "-o", str(out), "--no-recognise"]) == 0
    assert "0 annotations" in capsys.readouterr().err
    assert '"origin": ""' in out.read_text()
