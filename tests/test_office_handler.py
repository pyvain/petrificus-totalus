from pathlib import Path

import pymupdf

from petrificus_totalus import disarm_file, disarm_folder, iter_supported_mime_types
from petrificus_totalus._registry import detect_mime_type


def test_iter_supported_mime_types_includes_docx(tmp_path: Path, make_docx):
    src = make_docx(tmp_path / "report.docx")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_iter_supported_mime_types_includes_odt(tmp_path: Path, make_odt):
    src = make_odt(tmp_path / "report.odt")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_iter_supported_mime_types_includes_pptx(tmp_path: Path, make_pptx):
    src = make_pptx(tmp_path / "deck.pptx")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_docx_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_docx):
    src = make_docx(tmp_path / "report.docx", paragraphs=("Hello world",))

    result, _ = disarm_file(src)

    assert result == tmp_path / "report.docx.pdf"
    assert result.is_file()
    # An in-place disarm must not leave the original untrusted file behind
    # just because the safe form has a different extension.
    assert not src.exists()


def test_docx_disarm_preserves_pagination(tmp_path: Path, make_docx):
    src = make_docx(
        tmp_path / "multi.docx",
        paragraphs=("Page one content", "Page two content"),
        page_break=True,
    )

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 2
        assert "Page one content" in doc[0].get_text()
        assert "Page two content" in doc[1].get_text()


def test_docx_disarm_recovers_text_via_ocr(tmp_path: Path, make_docx):
    src = make_docx(tmp_path / "doc.docx", paragraphs=("Hello OCR World",))

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "Hello OCR World" in doc[0].get_text()


def test_docx_disarm_with_explicit_output_path_leaves_original(
    tmp_path: Path, make_docx
):
    src = make_docx(tmp_path / "in" / "report.docx")
    dst = tmp_path / "out" / "report.docx"

    result, _ = disarm_file(src, dst)

    assert result == tmp_path / "out" / "report.docx.pdf"
    assert result.is_file()
    assert src.is_file()  # writing to a separate location leaves the input untouched


def test_docx_disarm_folder_in_place_removes_originals(tmp_path: Path, make_docx):
    input_dir = tmp_path / "docs"
    # Two files so disarm_folder's process pool runs LibreOffice conversions
    # concurrently across worker processes -- confirms per-conversion profile
    # isolation actually avoids a profile-lock collision.
    make_docx(input_dir / "a.docx", paragraphs=("Hello world",))
    make_docx(input_dir / "b.docx", paragraphs=("Second document",))

    results = disarm_folder(input_dir)

    assert len(results) == 2
    statuses = {r.input_path.name: r.status for r in results}
    assert statuses == {"a.docx": "disarmed", "b.docx": "disarmed"}
    assert not (input_dir / "a.docx").exists()
    assert not (input_dir / "b.docx").exists()
    assert (input_dir / "a.docx.pdf").is_file()
    assert (input_dir / "b.docx.pdf").is_file()


def test_odt_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_odt):
    src = make_odt(tmp_path / "report.odt", paragraphs=("Hello world",))

    result, _ = disarm_file(src)

    assert result == tmp_path / "report.odt.pdf"
    assert result.is_file()
    # An in-place disarm must not leave the original untrusted file behind
    # just because the safe form has a different extension.
    assert not src.exists()


def test_odt_disarm_preserves_pagination(tmp_path: Path, make_odt):
    src = make_odt(
        tmp_path / "multi.odt",
        paragraphs=("Page one content", "Page two content"),
        page_break=True,
    )

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 2
        assert "Page one content" in doc[0].get_text()
        assert "Page two content" in doc[1].get_text()


def test_odt_disarm_recovers_text_via_ocr(tmp_path: Path, make_odt):
    src = make_odt(tmp_path / "doc.odt", paragraphs=("Hello OCR World",))

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "Hello OCR World" in doc[0].get_text()


def test_pptx_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_pptx):
    src = make_pptx(tmp_path / "deck.pptx", slide_texts=("Hello world",))

    result, _ = disarm_file(src)

    assert result == tmp_path / "deck.pptx.pdf"
    assert result.is_file()
    # An in-place disarm must not leave the original untrusted file behind
    # just because the safe form has a different extension.
    assert not src.exists()


def test_pptx_disarm_preserves_pagination(tmp_path: Path, make_pptx):
    src = make_pptx(
        tmp_path / "multi.pptx",
        slide_texts=("Slide one content", "Slide two content"),
    )

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 2
        assert "Slide one content" in doc[0].get_text()
        assert "Slide two content" in doc[1].get_text()


def test_pptx_disarm_recovers_text_via_ocr(tmp_path: Path, make_pptx):
    src = make_pptx(tmp_path / "deck.pptx", slide_texts=("Hello OCR World",))

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "Hello OCR World" in doc[0].get_text()


def test_pptx_disarm_with_explicit_output_path_leaves_original(
    tmp_path: Path, make_pptx
):
    src = make_pptx(tmp_path / "in" / "deck.pptx")
    dst = tmp_path / "out" / "deck.pptx"

    result, _ = disarm_file(src, dst)

    assert result == tmp_path / "out" / "deck.pptx.pdf"
    assert result.is_file()
    assert src.is_file()  # writing to a separate location leaves the input untouched


def test_pptx_disarm_folder_in_place_removes_originals(tmp_path: Path, make_pptx):
    input_dir = tmp_path / "decks"
    # Two files so disarm_folder's process pool runs LibreOffice conversions
    # concurrently across worker processes -- confirms per-conversion profile
    # isolation actually avoids a profile-lock collision.
    make_pptx(input_dir / "a.pptx", slide_texts=("Hello world",))
    make_pptx(input_dir / "b.pptx", slide_texts=("Second deck",))

    results = disarm_folder(input_dir)

    assert len(results) == 2
    statuses = {r.input_path.name: r.status for r in results}
    assert statuses == {"a.pptx": "disarmed", "b.pptx": "disarmed"}
    assert not (input_dir / "a.pptx").exists()
    assert not (input_dir / "b.pptx").exists()
    assert (input_dir / "a.pptx.pdf").is_file()
    assert (input_dir / "b.pptx.pdf").is_file()
