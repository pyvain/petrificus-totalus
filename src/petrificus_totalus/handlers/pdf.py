"""CDR handler for PDF documents.

Disarms by rasterizing every page to a bitmap and rebuilding a fresh PDF from
those bitmaps alone. This forces the output to be reconstructed from pixel
data only, discarding anything that isn't pixel data -- JavaScript, embedded
files, launch/form actions, fonts, the text layer -- the same way
handlers/image.py rebuilds raster images from decoded pixel data alone.

Rasterizing discards the text layer along with everything else, so the
result is run through ocrmypdf (Tesseract) to add back an invisible,
searchable text layer over the page images -- the pixels stay the sole
source of what renders, but the document is readable/searchable again. The
language passed to Tesseract is auto-detected (see _detect_languages) rather
than hardcoded, since a wrong language pack measurably hurts OCR accuracy.
English is always kept as a secondary language when it isn't the detected
primary, since documents often mix a local language with English terms.
"""

import logging
from pathlib import Path

import langdetect
import ocrmypdf
import pymupdf

from .._registry import register_handler

logger = logging.getLogger("petrificus-totalus")


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

    Prefers the document's existing text layer. Falls back to a quick OCR
    pass over the first page with a broad multi-language bootstrap set
    when there's no usable text layer -- i.e. a scanned PDF.

    raises ValueError when it is not possible to sample enough text
    """
    text = "\n".join(page.get_textpage().extractTEXT().strip() for page in src)
    if len(text) >= _MIN_SAMPLE_CHARS:
        return text

    logger.debug(f"Not enough text to sample. Falling back to broad first page OCR.")
    first_page = src[0]
    textpage = first_page.get_textpage_ocr(
        flags=0, language=_BOOTSTRAP_LANGUAGES, dpi=_RASTER_DPI, full=True
    )
    text += "\n" + textpage.extractTEXT()

    if len(text) < _MIN_SAMPLE_CHARS:
        raise ValueError("No text to sample")

    return text


def _detect_languages(src: pymupdf.Document) -> str:
    """Return a "+"-joined Tesseract language argument for ``src``.

    Keeps English as a secondary language whenever it isn't the detected
    primary, since documents often mix a local language with English words
    (product names, technical terms, code) that the primary-language
    dictionary alone would misread.
    """
    try:
        text = _sample_text(src)
    except ValueError:
        logger.warning(
            f"Cannot sample enough text for detection. Using the default language: {_DEFAULT_LANGUAGE}"
        )
        return _DEFAULT_LANGUAGE

    try:
        detected = langdetect.detect(text)
    except langdetect.LangDetectException as e:
        logger.error(
            f"langdetect raised an exception. Using the default language: {_DEFAULT_LANGUAGE}. Exception: {e}"
        )
        return _DEFAULT_LANGUAGE

    if detected == "unknown":
        logger.warning(
            f"langdetect did not detect any language. Using the default language: {_DEFAULT_LANGUAGE}"
        )
        return _DEFAULT_LANGUAGE

    try:
        primary = _LANGDETECT_TO_TESSERACT[detected]
    except KeyError:
        logger.error(
            f"langdetect's '{detected}' has no known equivalent among tesseract supported languages. Using the default language: {_DEFAULT_LANGUAGE}"
        )
        return _DEFAULT_LANGUAGE

    if primary == _DEFAULT_LANGUAGE:
        return primary
    return f"{primary}+{_DEFAULT_LANGUAGE}"


def disarm(input_path: Path, output_path: Path) -> None:
    with pymupdf.open(input_path) as src, pymupdf.open() as dst:
        logger.debug(f"{input_path}: detecting language...")
        language = _detect_languages(src)
        logger.debug(f"{input_path}: identified {language}")

        for page_number, page in enumerate(src.pages()):
            logger.debug(f"{input_path}: page {page_number}")
            pixmap = page.get_pixmap(dpi=_RASTER_DPI)
            new_page = dst.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pixmap)

        logger.debug(f"{input_path}: saving rasterized pdf {output_path}")
        dst.save(output_path)

    logger.debug(f"{input_path}: running ocr")
    ocrmypdf.ocr(
        output_path,
        output_path,
        language=language,
        output_type="pdf",
        progress_bar=False,
    )


register_handler("application/pdf")(disarm)
