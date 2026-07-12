from pathlib import Path

from PIL import Image

from petrificus_totalus import disarm_file


def test_jpeg_roundtrip_preserves_dimensions_and_format(tmp_path: Path, make_image):
    src = make_image(tmp_path / "photo.jpg", format="JPEG")
    original_bytes = src.read_bytes()

    result, _ = disarm_file(src)

    assert result == src
    with Image.open(src) as img:
        assert img.format == "JPEG"
        assert img.size == (16, 12)
    # The file was actually rewritten, not just copied through.
    assert src.read_bytes() != original_bytes


def test_png_roundtrip_preserves_alpha_channel(tmp_path: Path, make_image):
    src = make_image(tmp_path / "sprite.png", format="PNG", mode="RGBA")

    with Image.open(src) as before:
        before_pixel = before.convert("RGBA").getpixel((3, 4))

    disarm_file(src)

    with Image.open(src) as after:
        assert after.format == "PNG"
        assert after.mode == "RGBA"
        assert after.getpixel((3, 4)) == before_pixel


def test_jpeg_roundtrip_converts_non_rgb_intermediate_back_to_rgb(
    tmp_path: Path, make_image
):
    src = make_image(tmp_path / "gray.jpg", format="JPEG", mode="L")

    disarm_file(src)

    with Image.open(src) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"
        assert img.size == (16, 12)


def test_bmp_roundtrip(tmp_path: Path, make_image):
    src = make_image(tmp_path / "raw.bmp", format="BMP")

    disarm_file(src)

    with Image.open(src) as img:
        assert img.format == "BMP"
        assert img.size == (16, 12)


def test_disarm_file_writes_to_explicit_output_path(tmp_path: Path, make_image):
    src = make_image(tmp_path / "in" / "a.jpg", format="JPEG")
    dst = tmp_path / "out" / "a.jpg"

    result, _ = disarm_file(src, dst)

    assert result == dst
    assert dst.is_file()
    assert src.is_file()  # original untouched
    with Image.open(dst) as img:
        assert img.format == "JPEG"
