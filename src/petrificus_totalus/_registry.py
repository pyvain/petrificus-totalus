"""Handler registration and discovery.

Each module under :mod:`petrificus_totalus.handlers` registers itself against
one or more MIME types by decorating its ``petrify`` function with
:func:`register_handler`. To support a new file type, add a new module to
that package -- no changes to this file or to :mod:`petrificus_totalus.core`
are needed.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Callable

import magic

HandlerFunc = Callable[[Path, Path], None]

_REGISTRY: dict[str, HandlerFunc] = {}
_OUTPUT_SUFFIX: dict[str, str] = {}
_loaded = False


def register_handler(
    *mime_types: str, output_suffix: str | None = None
) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator registering ``func`` as the CDR handler for ``mime_types``.

    ``func`` must accept ``(input_path, output_path)`` and write a
    disarmed/reconstructed version of ``input_path`` to ``output_path``.
    MIME types are matched case-insensitively.

    Most handlers disarm a file while preserving its format, so the output
    path has the same extension as the input. Pass ``output_suffix`` (e.g.
    ``".pdf"``) for a handler that produces a different format instead --
    :func:`petrificus_totalus.core.petrify_file` will append it to the
    output filename (e.g. ``report.docx`` -> ``report.docx.pdf``) rather
    than assume the output extension matches the input.
    """

    def decorator(func: HandlerFunc) -> HandlerFunc:
        for mime_type in mime_types:
            normalized = mime_type.lower()
            if normalized in _REGISTRY:
                raise ValueError(
                    f"MIME type {normalized!r} is already registered to "
                    f"{_REGISTRY[normalized].__module__}.{_REGISTRY[normalized].__name__}"
                )
            _REGISTRY[normalized] = func
            if output_suffix is not None:
                _OUTPUT_SUFFIX[normalized] = output_suffix
        return func

    return decorator


def _load_handlers() -> None:
    global _loaded
    if _loaded:
        return
    from . import handlers

    for module_info in pkgutil.iter_modules(handlers.__path__):
        importlib.import_module(f"{handlers.__name__}.{module_info.name}")
    _loaded = True


def detect_mime_type(path: Path) -> str:
    """Sniff ``path``'s MIME type from its actual content.

    Deliberately ignores the file name/extension: an attacker can name a
    malicious payload ``photo.jpg`` to dodge extension-based dispatch, so the
    handler that runs must be chosen from what the bytes actually are.
    """
    return magic.from_file(str(path), mime=True)


def get_handler(mime_type: str) -> HandlerFunc | None:
    """Return the registered handler for ``mime_type``, if any."""
    _load_handlers()
    return _REGISTRY.get(mime_type.lower())


def get_output_suffix(mime_type: str) -> str | None:
    """Return the output suffix to append for ``mime_type``, if it has one.

    ``None`` means the handler preserves the input's format/extension.
    """
    _load_handlers()
    return _OUTPUT_SUFFIX.get(mime_type.lower())


def iter_supported_mime_types() -> tuple[str, ...]:
    """Return all currently registered MIME types, sorted."""
    _load_handlers()
    return tuple(sorted(_REGISTRY))
