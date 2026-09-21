"""The command line wrapper."""

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
