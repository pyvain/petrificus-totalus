from pathlib import Path

import pymupdf
import pytest

from petrificus_totalus import disarm_file
from petrificus_totalus.handlers import pdf as pdf_handler

# pymupdf's built-in base-14 fonts (Helvetica et al.) have no Cyrillic glyphs,
# so Cyrillic text inserted with them gets replaced with placeholder glyphs
# rather than the real characters. DejaVu Sans covers Cyrillic and is the
# default sans-serif font on Debian/Ubuntu.
_DEJAVU_SANS = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_requires_dejavu_sans = pytest.mark.skipif(
    not _DEJAVU_SANS.is_file(), reason="DejaVu Sans font not installed"
)


def _page_pixel(path: Path, page_index: int, xy: tuple[int, int] = (10, 10)):
    with pymupdf.open(path) as doc:
        return doc[page_index].get_pixmap().pixel(*xy)


def test_pdf_roundtrip_preserves_page_count_and_size(tmp_path: Path, make_pdf):
    src = make_pdf(tmp_path / "doc.pdf", page_colors=((1, 0, 0), (0, 1, 0), (0, 0, 1)))

    result = disarm_file(src)

    assert result == src
    with pymupdf.open(src) as doc:
        assert doc.page_count == 3
        for page in doc:
            assert (page.rect.width, page.rect.height) == (200, 300)


def test_pdf_roundtrip_preserves_page_colors(tmp_path: Path, make_pdf):
    src = make_pdf(
        tmp_path / "colors.pdf", page_colors=((1, 0, 0), (0, 1, 0), (0, 0, 1))
    )

    disarm_file(src)

    assert _page_pixel(src, 0) == (255, 0, 0)
    assert _page_pixel(src, 1) == (0, 255, 0)
    assert _page_pixel(src, 2) == (0, 0, 255)


def test_pdf_disarm_rewrites_bytes(tmp_path: Path, make_pdf):
    src = make_pdf(tmp_path / "doc.pdf")
    original_bytes = src.read_bytes()

    disarm_file(src)

    assert src.read_bytes() != original_bytes


def test_pdf_disarm_adds_searchable_ocr_text_layer(tmp_path: Path, make_pdf):
    src = make_pdf(
        tmp_path / "scanned.pdf",
        page_colors=((1, 1, 1),),
        text="Hello OCR World",
        size=(400, 300),
    )

    with pymupdf.open(src) as before:
        # The source page has real text objects, but rasterizing to a bitmap
        # in the first CDR stage would normally discard them entirely.
        assert before[0].get_textpage().extractTEXT().strip() == "Hello OCR World"

    disarm_file(src)

    with pymupdf.open(src) as after:
        assert after[0].get_textpage().extractTEXT().strip() == "Hello OCR World"


def test_detect_languages_keeps_english_as_secondary_for_non_english_primary():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text(
            (20, 150),
            "Ceci est un texte suffisamment long en francais pour la detection",
            fontsize=14,
        )
        assert pdf_handler._detect_languages(doc) == "fra+eng"


def test_detect_languages_does_not_duplicate_english_primary():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text(
            (20, 150),
            "This is plainly a long enough sentence of English text",
            fontsize=14,
        )
        assert pdf_handler._detect_languages(doc) == "eng"


def test_detect_languages_falls_back_to_default_for_blank_document():
    with pymupdf.open() as doc:
        doc.new_page(width=400, height=300)
        assert pdf_handler._detect_languages(doc) == pdf_handler._DEFAULT_LANGUAGE


@_requires_dejavu_sans
def test_detect_languages_keeps_english_secondary_for_russian_primary():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text(
            (20, 150),
            "Это достаточно длинный текст на русском языке для определения",
            fontsize=14,
            fontfile=str(_DEJAVU_SANS),
            fontname="F0",
        )
        assert pdf_handler._detect_languages(doc) == "rus+eng"


@_requires_dejavu_sans
def test_pdf_disarm_recognizes_mixed_russian_and_english_text(tmp_path: Path):
    # Documents often mix a local language with English terms (product names,
    # technical jargon); the "rus" pack alone would badly mangle "software
    # update" -- this only passes if English was kept as a secondary language.
    text = "Привет мир software update готово"
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=300)
        page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
        page.insert_text(
            (20, 150),
            text,
            fontsize=20,
            color=(0, 0, 0),
            fontfile=str(_DEJAVU_SANS),
            fontname="F0",
        )
        src = tmp_path / "mixed.pdf"
        doc.save(src)

    disarm_file(src)

    with pymupdf.open(src) as after:
        recovered = after[0].get_textpage().extractTEXT().strip()

    assert recovered == text


def test_pdf_disarm_recognizes_non_english_text_via_detected_language(
    tmp_path: Path, make_pdf
):
    # Accented French text that an English-only OCR pass reliably mangles
    # (it drops accents almost entirely) but a correctly detected "fra" pack
    # mostly preserves -- Tesseract isn't pixel-perfect, so assert on
    # accent recovery rather than an exact string match to avoid flakiness.
    text = "Mon café préféré est ici"
    src = make_pdf(
        tmp_path / "french.pdf", page_colors=((1, 1, 1),), text=text, size=(400, 300)
    )

    disarm_file(src)

    with pymupdf.open(src) as after:
        recovered = after[0].get_textpage().extractTEXT().strip()

    assert "café" in recovered
    assert recovered.count("é") >= 3


def test_disarm_file_writes_pdf_to_explicit_output_path(tmp_path: Path, make_pdf):
    src = make_pdf(tmp_path / "in" / "doc.pdf")
    dst = tmp_path / "out" / "doc.pdf"

    result = disarm_file(src, dst)

    assert result == dst
    assert dst.is_file()
    assert src.is_file()  # original untouched
    with pymupdf.open(dst) as doc:
        assert doc.page_count == 1
