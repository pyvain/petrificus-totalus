"""Modular content disarm & reconstruction (CDR) library.

Transforms untrusted files into versions that cannot reasonably exploit a
reader for that file type, preserving the original file type wherever
possible. See :func:`disarm_file` and :func:`disarm_folder`.
"""

from ._registry import iter_supported_mime_types
from .core import (
    DisarmResult,
    UnsupportedFileTypeError,
    disarm_file,
    disarm_folder,
)

__all__ = [
    "DisarmResult",
    "UnsupportedFileTypeError",
    "iter_supported_mime_types",
    "disarm_file",
    "disarm_folder",
]
