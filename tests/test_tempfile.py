from pathlib import Path

import pytest

from petrificus_totalus.helpers.tempfile import temp_dir, temp_file


def test_temp_dir_created_inside_given_dir(tmp_path: Path):
    scratch = tmp_path / "scratch"

    with temp_dir(parent_dir=scratch) as path:
        assert path.is_dir()
        assert path.parent == scratch


def test_temp_dir_removed_on_normal_exit(tmp_path: Path):
    with temp_dir(parent_dir=tmp_path) as path:
        (path / "some_file").write_text("data")

    assert not path.exists()


def test_temp_dir_removed_on_error(tmp_path: Path):
    with pytest.raises(ValueError):
        with temp_dir(parent_dir=tmp_path) as path:
            (path / "some_file").write_text("data")
            raise ValueError("boom")

    assert not path.exists()


def test_temp_dir_promoted_via_rename_is_left_alone(tmp_path: Path):
    destination = tmp_path / "final"

    with temp_dir(parent_dir=tmp_path) as path:
        (path / "some_file").write_text("data")
        path.rename(destination)

    assert destination.is_dir()
    assert (destination / "some_file").read_text() == "data"


def test_temp_dir_derives_parent_and_prefix_from_dirname(tmp_path: Path):
    dirname = tmp_path / "scratch" / "final"

    with temp_dir(dirname=dirname, prefix=".tmp-") as path:
        assert path.is_dir()
        assert path.parent == dirname.parent
        assert path.name.startswith(".tmp-final")


def test_temp_file_created_inside_given_dir(tmp_path: Path):
    scratch = tmp_path / "scratch"

    with temp_file(parent_dir=scratch) as path:
        assert path.is_file()
        assert path.parent == scratch


def test_temp_file_removed_on_normal_exit(tmp_path: Path):
    with temp_file(parent_dir=tmp_path) as path:
        path.write_text("data")

    assert not path.exists()


def test_temp_file_removed_on_error(tmp_path: Path):
    with pytest.raises(ValueError):
        with temp_file(parent_dir=tmp_path) as path:
            path.write_text("data")
            raise ValueError("boom")

    assert not path.exists()


def test_temp_file_promoted_via_rename_is_left_alone(tmp_path: Path):
    destination = tmp_path / "final.txt"

    with temp_file(parent_dir=tmp_path) as path:
        path.write_text("data")
        path.rename(destination)

    assert destination.read_text() == "data"


def test_temp_file_respects_suffix(tmp_path: Path):
    with temp_file(parent_dir=tmp_path, suffix=".pdf") as path:
        assert path.suffix == ".pdf"


def test_temp_file_derives_parent_and_prefix_from_filename(tmp_path: Path):
    filename = tmp_path / "scratch" / "final.txt"

    with temp_file(filename=filename, prefix=".tmp-") as path:
        assert path.is_file()
        assert path.parent == filename.parent
        assert path.name.startswith(".tmp-final.txt")
