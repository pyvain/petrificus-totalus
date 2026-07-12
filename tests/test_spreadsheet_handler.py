from pathlib import Path

import pymupdf

from petrificus_totalus import disarm_file, disarm_folder, iter_supported_mime_types
from petrificus_totalus._registry import detect_mime_type


def test_iter_supported_mime_types_includes_xlsx(tmp_path: Path, make_xlsx):
    src = make_xlsx(tmp_path / "report.xlsx")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_iter_supported_mime_types_includes_ods(tmp_path: Path, make_ods):
    src = make_ods(tmp_path / "report.ods")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_xlsx_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_xlsx):
    src = make_xlsx(tmp_path / "report.xlsx")

    result, _ = disarm_file(src)

    assert result == tmp_path / "report.xlsx.pdf"
    assert result.is_file()
    # An in-place disarm must not leave the original untrusted file behind
    # just because the safe form has a different extension.
    assert not src.exists()


def test_xlsx_disarm_recovers_text_via_ocr(tmp_path: Path, make_xlsx):
    src = make_xlsx(tmp_path / "sheet.xlsx", columns=2, rows=2)

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "r1c1" in doc[0].get_text()


def test_xlsx_disarm_with_explicit_output_path_leaves_original(tmp_path: Path, make_xlsx):
    src = make_xlsx(tmp_path / "in" / "report.xlsx")
    dst = tmp_path / "out" / "report.xlsx"

    result, _ = disarm_file(src, dst)

    assert result == tmp_path / "out" / "report.xlsx.pdf"
    assert result.is_file()
    assert src.is_file()  # writing to a separate location leaves the input untouched


def test_xlsx_disarm_folder_in_place_removes_originals(tmp_path: Path, make_xlsx):
    input_dir = tmp_path / "sheets"
    # Two files so disarm_folder's process pool runs LibreOffice conversions
    # concurrently across worker processes -- confirms per-conversion UNO
    # pipe/profile isolation actually avoids a collision.
    make_xlsx(input_dir / "a.xlsx")
    make_xlsx(input_dir / "b.xlsx")

    results = disarm_folder(input_dir)

    assert len(results) == 2
    statuses = {r.input_path.name: r.status for r in results}
    assert statuses == {"a.xlsx": "disarmed", "b.xlsx": "disarmed"}
    assert not (input_dir / "a.xlsx").exists()
    assert not (input_dir / "b.xlsx").exists()
    assert (input_dir / "a.xlsx.pdf").is_file()
    assert (input_dir / "b.xlsx.pdf").is_file()


def test_xlsx_disarm_fits_all_columns_on_one_page_width(tmp_path: Path, make_xlsx):
    # Wide enough that LibreOffice's default fixed page width would split
    # the sheet across separate pages horizontally, cutting later columns
    # off from earlier ones -- the exact problem the auto-widened page
    # width is meant to prevent.
    src = make_xlsx(tmp_path / "wide.xlsx", columns=20, rows=5)

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        first_page_text = doc[0].get_text()
        assert "r1c1" in first_page_text
        assert "r1c20" in first_page_text


def test_xlsx_disarm_fits_varied_column_widths_on_one_page(tmp_path: Path, make_xlsx):
    # Uniform column widths happen to sum to a whole number of twips, so
    # they can't reproduce the rounding bug this guards against: Calc lays
    # out each column in twips (1/1440 in) independently, but UNO reports
    # widths in 1/100 mm, so summing the raw 1/100 mm widths and converting
    # once to a page width silently loses up to a twip per column. These
    # widths (irrational relative to a twip) reliably lost enough width for
    # the last column to spill onto its own page before that rounding was
    # fixed to round each column up to whole twips before summing.
    widths = (11.24, 39.05, 35.79, 15.95, 25.32, 23.53, 31.41, 36.76)
    src = make_xlsx(tmp_path / "varied.xlsx", columns=len(widths), rows=3, column_widths=widths)

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 1
        first_page_text = doc[0].get_text()
        assert "r1c1" in first_page_text
        assert f"r1c{len(widths)}" in first_page_text


def test_ods_disarm_produces_pdf_and_removes_original(tmp_path: Path, make_ods):
    src = make_ods(tmp_path / "report.ods")

    result, _ = disarm_file(src)

    assert result == tmp_path / "report.ods.pdf"
    assert result.is_file()
    # An in-place disarm must not leave the original untrusted file behind
    # just because the safe form has a different extension.
    assert not src.exists()


def test_ods_disarm_recovers_text_via_ocr(tmp_path: Path, make_ods):
    src = make_ods(tmp_path / "sheet.ods", columns=2, rows=2)

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert "r1c1" in doc[0].get_text()


def test_ods_disarm_fits_all_columns_on_one_page_width(tmp_path: Path, make_ods):
    # Wide enough that LibreOffice's default fixed page width would split
    # the sheet across separate pages horizontally, cutting later columns
    # off from earlier ones -- the exact problem the auto-widened page
    # width is meant to prevent.
    src = make_ods(tmp_path / "wide.ods", columns=20, rows=5)

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        first_page_text = doc[0].get_text()
        assert "r1c1" in first_page_text
        assert "r1c20" in first_page_text


def test_ods_disarm_fits_varied_column_widths_on_one_page(tmp_path: Path, make_ods):
    widths_mm = (31.24, 59.05, 55.79, 35.95, 45.32, 43.53, 51.41, 56.76)
    src = make_ods(
        tmp_path / "varied.ods", columns=len(widths_mm), rows=3, column_widths_mm=widths_mm
    )

    result, _ = disarm_file(src)

    with pymupdf.open(result) as doc:
        assert doc.page_count == 1
        first_page_text = doc[0].get_text()
        assert "r1c1" in first_page_text
        assert f"r1c{len(widths_mm)}" in first_page_text
