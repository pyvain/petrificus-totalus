from pathlib import Path

from petrificus_totalus.cli import main
from petrificus_totalus.core import PetrifyResult


def test_cli_petrifies_single_file_in_place(tmp_path: Path, make_image, capsys):
    src = make_image(tmp_path / "photo.jpg", format="JPEG")
    original_bytes = src.read_bytes()

    exit_code = main([str(src)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == str(src)
    assert src.read_bytes() != original_bytes


def test_cli_petrifies_single_file_with_explicit_output(tmp_path: Path, make_image, capsys):
    src = make_image(tmp_path / "in" / "photo.jpg", format="JPEG")
    dst = tmp_path / "out" / "photo.jpg"

    exit_code = main([str(src), "--output", str(dst)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == str(dst)
    assert dst.is_file()
    assert src.is_file()


def test_cli_missing_file_returns_error(tmp_path: Path, capsys):
    exit_code = main([str(tmp_path / "does-not-exist.jpg")])

    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_unsupported_file_returns_error(tmp_path: Path, capsys):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello")

    exit_code = main([str(unsupported)])

    assert exit_code == 1
    assert "No CDR handler registered" in capsys.readouterr().err


def test_cli_petrifies_folder_prints_summary(tmp_path: Path, make_image, capsys):
    input_dir = tmp_path / "docs"
    make_image(input_dir / "a.jpg", format="JPEG")
    (input_dir / "readme.txt").write_text("not an image")

    exit_code = main([str(input_dir)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "1 petrified, 1 skipped, 0 failed"


def test_cli_folder_with_failures_reports_nonzero_exit(tmp_path: Path, monkeypatch, capsys):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    fake_results = [
        PetrifyResult(input_dir / "bad.jpg", None, "failed", "boom"),
        PetrifyResult(input_dir / "good.jpg", input_dir / "good.jpg", "petrified"),
    ]
    monkeypatch.setattr("petrificus_totalus.cli.petrify_folder", lambda *a, **k: fake_results)

    exit_code = main([str(input_dir)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAILED" in captured.err
    assert "boom" in captured.err
    assert captured.out.strip() == "1 petrified, 0 skipped, 1 failed"


def test_cli_folder_max_workers_is_forwarded(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    captured_kwargs = {}

    def fake_petrify_folder(input_dir, output_dir, *, max_workers=None):
        captured_kwargs["max_workers"] = max_workers
        return []

    monkeypatch.setattr("petrificus_totalus.cli.petrify_folder", fake_petrify_folder)

    main([str(input_dir), "--max-workers", "3"])

    assert captured_kwargs["max_workers"] == 3
