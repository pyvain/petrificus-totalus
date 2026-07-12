from pathlib import Path

from petrificus_totalus import disarm_file, iter_supported_mime_types
from petrificus_totalus._registry import detect_mime_type


def test_iter_supported_mime_types_includes_text_plain(tmp_path: Path, make_text_file):
    src = make_text_file(tmp_path / "notes.txt")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_iter_supported_mime_types_includes_csv(tmp_path: Path, make_csv):
    src = make_csv(tmp_path / "data.csv")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_text_disarm_in_place_preserves_content(tmp_path: Path, make_text_file):
    src = make_text_file(tmp_path / "notes.txt", content="Hello world\n")

    result = disarm_file(src)

    assert result == src
    assert src.read_text() == "Hello world\n"


def test_csv_disarm_in_place_preserves_content(tmp_path: Path, make_csv):
    src = make_csv(tmp_path / "data.csv", rows=(("a", "b", "c"), ("1", "2", "3")))
    original_bytes = src.read_bytes()

    result = disarm_file(src)

    assert result == src
    assert src.read_bytes() == original_bytes


def test_empty_file_disarm_in_place(tmp_path: Path):
    src = tmp_path / "empty.bin"
    src.write_bytes(b"")

    result = disarm_file(src)

    assert result == src
    assert src.read_bytes() == b""


def test_text_disarm_with_explicit_output_path_leaves_original(
    tmp_path: Path, make_text_file
):
    src = make_text_file(tmp_path / "in" / "notes.txt", content="Hello world\n")
    dst = tmp_path / "out" / "notes.txt"

    result = disarm_file(src, dst)

    assert result == dst
    assert dst.read_text() == "Hello world\n"
    assert src.is_file()  # writing to a separate location leaves the input untouched
