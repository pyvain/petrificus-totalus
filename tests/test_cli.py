from pathlib import Path

from petrificus_totalus.cli import main
from petrificus_totalus.core import DisarmResult


def test_cli_disarms_single_file_in_place(tmp_path: Path, make_image, capsys):
    src = make_image(tmp_path / "photo.jpg", format="JPEG")
    original_bytes = src.read_bytes()

    exit_code = main([str(src)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == str(src)
    assert src.read_bytes() != original_bytes


def test_cli_disarms_single_file_with_explicit_output(
    tmp_path: Path, make_image, capsys
):
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


def test_cli_unsupported_file_returns_error(tmp_path: Path, make_unsupported, capsys):
    unsupported = make_unsupported(tmp_path / "notes.bin")

    exit_code = main([str(unsupported)])

    assert exit_code == 1
    assert "No CDR handler registered" in capsys.readouterr().err


def test_cli_disarms_folder_prints_summary(
    tmp_path: Path, make_image, make_unsupported, capsys
):
    input_dir = tmp_path / "docs"
    make_image(input_dir / "a.jpg", format="JPEG")
    make_unsupported(input_dir / "payload.bin")

    exit_code = main([str(input_dir)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "1 disarmed, 0 trusted, 1 skipped, 0 failed"


def test_cli_folder_with_failures_reports_nonzero_exit(
    tmp_path: Path, monkeypatch, capsys
):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    fake_results = [
        DisarmResult(input_dir / "bad.jpg", None, "failed", "boom"),
        DisarmResult(input_dir / "good.jpg", input_dir / "good.jpg", "disarmed"),
    ]
    monkeypatch.setattr(
        "petrificus_totalus.cli.disarm_folder", lambda *a, **k: fake_results
    )

    exit_code = main([str(input_dir)])

    captured = capsys.readouterr()
    assert exit_code == 1
    # assert "FAILED" in captured.err
    # assert "boom" in captured.err
    assert captured.out.strip() == "1 disarmed, 0 trusted, 0 skipped, 1 failed"


def test_cli_folder_max_workers_is_forwarded(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    captured_kwargs = {}

    def fake_disarm_folder(
        input_dir,
        output_dir,
        *,
        max_workers=None,
        trusted_mime_types=None,
        delete_input_on_success=False,
    ):
        captured_kwargs["max_workers"] = max_workers
        return []

    monkeypatch.setattr("petrificus_totalus.cli.disarm_folder", fake_disarm_folder)

    main([str(input_dir), "--max-workers", "3"])

    assert captured_kwargs["max_workers"] == 3


def test_cli_trust_mime_is_forwarded_for_file(tmp_path: Path, make_image, monkeypatch):
    src = make_image(tmp_path / "photo.jpg", format="JPEG")

    captured_kwargs = {}

    def fake_disarm_file(
        input_path,
        output_path=None,
        *,
        trusted_mime_types=None,
        delete_input_on_success=False,
    ):
        captured_kwargs["trusted_mime_types"] = trusted_mime_types
        return input_path, False

    monkeypatch.setattr("petrificus_totalus.cli.disarm_file", fake_disarm_file)

    main(
        [
            str(src),
            "--trust-mime",
            "image/jpeg",
            "--trust-mime",
            "application/pdf",
        ]
    )

    assert captured_kwargs["trusted_mime_types"] == ["image/jpeg", "application/pdf"]


def test_cli_trust_mime_is_forwarded_for_folder(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    captured_kwargs = {}

    def fake_disarm_folder(
        input_dir,
        output_dir,
        *,
        max_workers=None,
        trusted_mime_types=None,
        delete_input_on_success=False,
    ):
        captured_kwargs["trusted_mime_types"] = trusted_mime_types
        return []

    monkeypatch.setattr("petrificus_totalus.cli.disarm_folder", fake_disarm_folder)

    main([str(input_dir), "--trust-mime", "image/jpeg"])

    assert captured_kwargs["trusted_mime_types"] == ["image/jpeg"]


def test_cli_delete_input_on_success_is_forwarded_for_file(
    tmp_path: Path, make_image, monkeypatch
):
    src = make_image(tmp_path / "photo.jpg", format="JPEG")

    captured_kwargs = {}

    def fake_disarm_file(
        input_path,
        output_path=None,
        *,
        trusted_mime_types=None,
        delete_input_on_success=False,
    ):
        captured_kwargs["delete_input_on_success"] = delete_input_on_success
        return input_path, False

    monkeypatch.setattr("petrificus_totalus.cli.disarm_file", fake_disarm_file)

    main([str(src), "--delete-input-on-success"])

    assert captured_kwargs["delete_input_on_success"] is True


def test_cli_delete_input_on_success_is_forwarded_for_folder(
    tmp_path: Path, monkeypatch
):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    captured_kwargs = {}

    def fake_disarm_folder(
        input_dir,
        output_dir,
        *,
        max_workers=None,
        trusted_mime_types=None,
        delete_input_on_success=False,
    ):
        captured_kwargs["delete_input_on_success"] = delete_input_on_success
        return []

    monkeypatch.setattr("petrificus_totalus.cli.disarm_folder", fake_disarm_folder)

    main([str(input_dir), "--delete-input-on-success"])

    assert captured_kwargs["delete_input_on_success"] is True
