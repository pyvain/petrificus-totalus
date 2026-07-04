"""CDR handler for PDF documents.

Disarms by rasterizing every page to a bitmap and rebuilding a fresh PDF from
those bitmaps alone. This forces the output to be reconstructed from pixel
data only, discarding anything that isn't pixel data -- JavaScript, embedded
files, launch/form actions, fonts, the text layer -- the same way
handlers/image.py rebuilds raster images from decoded pixel data alone.

Pages are rendered and re-inserted one at a time, each written to a temp file
and referenced by path rather than held decoded in memory, so peak memory
stays roughly constant regardless of page count.

Rasterizing discards the text layer along with everything else, so the
result is run through ocrmypdf (Tesseract) to add back an invisible,
searchable text layer over the page images -- the pixels stay the sole
source of what renders, but the document is readable/searchable again. The
language passed to Tesseract is auto-detected (see _detect_languages) rather
than hardcoded, since a wrong language pack measurably hurts OCR accuracy.
English is always kept as a secondary language when it isn't the detected
primary, since documents often mix a local language with English terms.
"""

import tempfile
from pathlib import Path

import langdetect
import ocrmypdf
import pymupdf

from .._registry import register_handler

_RASTER_DPI = 300
_DEFAULT_LANGUAGE = "eng"

# Used only to sample enough legible text to run langdetect against when a
# document has no existing text layer (see _sample_text). Doesn't need to
# match the document's real language -- it just has to be broad enough that
# Tesseract produces roughly readable text regardless of what the real
# language turns out to be, covering the languages _LANGDETECT_TO_TESSERACT
# knows how to map plus a spread of major scripts.
_BOOTSTRAP_LANGUAGES = "eng+fra+deu+spa+por+ita+nld+rus+ara+chi_sim+jpn+kor+hin"

_MIN_SAMPLE_CHARS = 30

# langdetect's ISO 639-1 (or zh-cn/zh-tw) codes mapped to the corresponding
# tesseract traineddata language code.
_LANGDETECT_TO_TESSERACT = {
    "af": "afr", "ar": "ara", "bg": "bul", "bn": "ben", "ca": "cat",
    "cs": "ces", "cy": "cym", "da": "dan", "de": "deu", "el": "ell",
    "en": "eng", "es": "spa", "et": "est", "fa": "fas", "fi": "fin",
    "fr": "fra", "gu": "guj", "he": "heb", "hi": "hin", "hr": "hrv",
    "hu": "hun", "id": "ind", "it": "ita", "ja": "jpn", "kn": "kan",
    "ko": "kor", "lt": "lit", "lv": "lav", "mk": "mkd", "ml": "mal",
    "mr": "mar", "ne": "nep", "nl": "nld", "no": "nor", "pa": "pan",
    "pl": "pol", "pt": "por", "ro": "ron", "ru": "rus", "sk": "slk",
    "sl": "slv", "so": "som", "sq": "sqi", "sv": "swe", "sw": "swa",
    "ta": "tam", "te": "tel", "th": "tha", "tl": "fil", "tr": "tur",
    "uk": "ukr", "ur": "urd", "vi": "vie", "zh-cn": "chi_sim", "zh-tw": "chi_tra",
}  # fmt: skip


def _sample_text(src: pymupdf.Document) -> str:
    """Grab enough text from ``src`` to guess its language.

    Prefers the document's existing text layer (cheap, no OCR needed). Falls
    back to a quick OCR pass over the first page with a broad multi-language
    bootstrap set when there's no usable text layer -- i.e. a scanned PDF,
    which is exactly the case where getting the OCR language right matters
    most.
    """
    text = "\n".join(page.get_text() for page in src)
    if len(text.strip()) >= _MIN_SAMPLE_CHARS:
        return text

    first_page = src[0]
    textpage = first_page.get_textpage_ocr(
        flags=0, language=_BOOTSTRAP_LANGUAGES, dpi=_RASTER_DPI, full=True
    )
    return first_page.get_text(textpage=textpage)


def _detect_languages(src: pymupdf.Document) -> str:
    """Return a "+"-joined Tesseract language argument for ``src``.

    Keeps English as a secondary language whenever it isn't the detected
    primary, since documents often mix a local language with English words
    (product names, technical terms, code) that the primary-language
    dictionary alone would misread.
    """
    text = _sample_text(src)
    if len(text.strip()) < _MIN_SAMPLE_CHARS:
        return _DEFAULT_LANGUAGE
    try:
        detected = langdetect.detect(text)
    except langdetect.LangDetectException:
        return _DEFAULT_LANGUAGE

    primary = _LANGDETECT_TO_TESSERACT.get(detected, _DEFAULT_LANGUAGE)
    if primary == _DEFAULT_LANGUAGE:
        return primary
    return f"{primary}+{_DEFAULT_LANGUAGE}"


def petrify(input_path: Path, output_path: Path) -> None:
    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        pymupdf.open(input_path) as src,
        pymupdf.open() as out,
    ):
        language = _detect_languages(src)

        for page_number, page in enumerate(src):
            pixmap = page.get_pixmap(dpi=_RASTER_DPI)
            page_path = Path(tmp_dir) / f"page-{page_number}.png"
            pixmap.save(page_path)
            del pixmap

            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, filename=page_path)

        rasterized_path = Path(tmp_dir) / "rasterized.pdf"
        out.save(rasterized_path)

        ocrmypdf.ocr(
            rasterized_path,
            output_path,
            language=language,
            output_type="pdf",
            progress_bar=False,
        )


register_handler("application/pdf")(petrify)
