from pathlib import Path

import docx
import openpyxl
import pymupdf
import pytest
from openpyxl.utils import get_column_letter
from PIL import Image


@pytest.fixture
def make_image():
    """Factory fixture: writes a small test image to disk and returns its path."""

    def _make(path: Path, *, format: str, mode: str = "RGB", size: tuple[int, int] = (16, 12)):
        image = Image.new(mode, size)
        for x in range(size[0]):
            for y in range(size[1]):
                if mode == "RGBA":
                    image.putpixel((x, y), ((x * 7) % 256, (y * 13) % 256, 128, 200))
                else:
                    image.putpixel((x, y), ((x * 7) % 256, (y * 13) % 256, 128))
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format=format)
        return path

    return _make


@pytest.fixture
def make_pdf():
    """Factory fixture: writes a small multi-page test PDF to disk and returns its path."""

    def _make(
        path: Path,
        *,
        page_colors: tuple[tuple[float, float, float], ...] = ((1, 0, 0),),
        text: str | None = None,
        size: tuple[float, float] = (200, 300),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open() as doc:
            for color in page_colors:
                page = doc.new_page(width=size[0], height=size[1])
                page.draw_rect(page.rect, color=color, fill=color)
                if text:
                    page.insert_text((20, 150), text, fontsize=24, color=(0, 0, 0))
            doc.save(path)
        return path

    return _make


@pytest.fixture
def make_docx():
    """Factory fixture: writes a small test .docx to disk and returns its path."""

    def _make(path: Path, *, paragraphs: tuple[str, ...] = ("Hello world",), page_break: bool = False):
        path.parent.mkdir(parents=True, exist_ok=True)
        document = docx.Document()
        for i, text in enumerate(paragraphs):
            if page_break and i > 0:
                document.add_page_break()
            document.add_paragraph(text)
        document.save(path)
        return path

    return _make


@pytest.fixture
def make_unsupported():
    """Factory fixture: writes a file with no registered CDR handler to disk.

    Content is arbitrary bytes rather than text, since dispatch is by
    sniffed content and plain text is a supported MIME type.
    """

    def _make(path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(range(256)))
        return path

    return _make


@pytest.fixture
def make_xlsx():
    """Factory fixture: writes a small test .xlsx to disk and returns its path."""

    def _make(
        path: Path,
        *,
        columns: int = 4,
        rows: int = 3,
        column_widths: tuple[float, ...] | None = None,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        for row in range(1, rows + 1):
            for col in range(1, columns + 1):
                sheet.cell(row=row, column=col, value=f"r{row}c{col}")
        if column_widths is not None:
            for col, width in enumerate(column_widths, start=1):
                sheet.column_dimensions[get_column_letter(col)].width = width
        workbook.save(path)
        return path

    return _make
