"""Modular content disarm & reconstruction (CDR) library.

Transforms untrusted files into versions that cannot reasonably exploit a
reader for that file type, preserving the original file type wherever
possible. See :func:`petrify_file` and :func:`petrify_folder`.
"""

from ._registry import iter_supported_mime_types
from .core import (
    PetrifyResult,
    UnsupportedFileTypeError,
    petrify_file,
    petrify_folder,
)

__all__ = [
    "PetrifyResult",
    "UnsupportedFileTypeError",
    "iter_supported_mime_types",
    "petrify_file",
    "petrify_folder",
]
