from pathlib import Path

import pymupdf

from petrificus_totalus import disarm_file, disarm_folder, iter_supported_mime_types

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_iter_supported_mime_types_includes_docx():
    assert _DOCX_MIME in iter_supported_mime_types()


def test_docx_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_docx):
    src = make_docx(tmp_path / "report.docx", paragraphs=("Hello world",))

    result = disarm_file(src)

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

    result = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 2
        assert "Page one content" in doc[0].get_text()
        assert "Page two content" in doc[1].get_text()


def test_docx_disarm_recovers_text_via_ocr(tmp_path: Path, make_docx):
    src = make_docx(tmp_path / "doc.docx", paragraphs=("Hello OCR World",))

    result = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "Hello OCR World" in doc[0].get_text()


def test_docx_disarm_with_explicit_output_path_leaves_original(
    tmp_path: Path, make_docx
):
    src = make_docx(tmp_path / "in" / "report.docx")
    dst = tmp_path / "out" / "report.docx"

    result = disarm_file(src, dst)

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
