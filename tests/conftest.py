from pathlib import Path

import docx
import pymupdf
import pytest
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
