from pathlib import Path

import pytest
from PIL import Image

from petrificus_totalus import (
    UnsupportedFileTypeError,
    iter_supported_mime_types,
    petrify_file,
    petrify_folder,
)


def test_iter_supported_mime_types_includes_registered_handlers():
    mime_types = iter_supported_mime_types()
    assert {"image/jpeg", "image/png", "image/bmp", "application/pdf"} <= set(mime_types)


def test_petrify_file_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        petrify_file(tmp_path / "does-not-exist.jpg")


def test_petrify_file_unsupported_extension_raises(tmp_path: Path):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello")

    with pytest.raises(UnsupportedFileTypeError):
        petrify_file(unsupported)


def test_petrify_file_dispatches_on_content_not_extension(tmp_path: Path, make_image):
    # A PNG mislabeled with a .jpg extension must still be handled as a PNG:
    # dispatch is based on sniffed content, not the (untrustworthy) file name.
    mislabeled = make_image(tmp_path / "actually-a-png.jpg", format="PNG", mode="RGBA")

    petrify_file(mislabeled)

    with Image.open(mislabeled) as img:
        assert img.format == "PNG"


def test_petrify_folder_mirrors_structure_into_output_dir(tmp_path: Path, make_image):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    make_image(input_dir / "a.jpg", format="JPEG")
    make_image(input_dir / "nested" / "b.png", format="PNG", mode="RGBA")
    (input_dir / "readme.txt").parent.mkdir(parents=True, exist_ok=True)
    (input_dir / "readme.txt").write_text("not an image")

    results = petrify_folder(input_dir, output_dir)

    assert len(results) == 3
    statuses = {r.input_path.name: r.status for r in results}
    assert statuses["a.jpg"] == "petrified"
    assert statuses["b.png"] == "petrified"
    assert statuses["readme.txt"] == "skipped"

    assert (output_dir / "a.jpg").is_file()
    assert (output_dir / "nested" / "b.png").is_file()
    # Unsupported files are never copied through unsanitized.
    assert not (output_dir / "readme.txt").exists()
    # Input files are left untouched when writing to a separate output_dir.
    assert (input_dir / "a.jpg").is_file()


def test_petrify_folder_in_place(tmp_path: Path, make_image):
    input_dir = tmp_path / "docs"
    src = make_image(input_dir / "photo.jpg", format="JPEG")
    original_bytes = src.read_bytes()

    results = petrify_folder(input_dir)

    assert len(results) == 1
    assert results[0].status == "petrified"
    assert results[0].output_path == src
    assert src.read_bytes() != original_bytes


def test_petrify_folder_requires_existing_directory(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        petrify_folder(tmp_path / "nope")
