"""Core CDR orchestration: :func:`disarm_file` and :func:`disarm_folder`."""

import concurrent.futures
import dataclasses
import logging
import os
import shutil
from pathlib import Path
from typing import Iterable, Literal

from ._registry import detect_mime_type, get_handler, get_output_suffix

logger = logging.getLogger("petrificus-totalus")


class UnsupportedFileTypeError(Exception):
    """Raised when no CDR handler is registered for a file's MIME type."""


@dataclasses.dataclass(frozen=True)
class DisarmResult:
    """Outcome of disarming a single file within a :func:`disarm_folder` run."""

    input_path: Path
    output_path: Path | None
    status: Literal["disarmed", "skipped", "failed"]
    detail: str | None = None


def disarm_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    trusted_mime_types: Iterable[str] | None = None,
) -> Path:
    """Run content disarm & reconstruction on a single file.

    Dispatches to the handler registered for the MIME type sniffed from
    ``input_path``'s actual content. Writes to ``output_path`` if given,
    otherwise overwrites ``input_path`` in place.

    If the sniffed MIME type is in ``trusted_mime_types`` (matched
    case-insensitively), the file is copied through as-is instead of being
    dispatched to a handler.

    Most handlers preserve the input's format, so the output has the same
    extension. A handler may instead be registered with an ``output_suffix``
    (see :func:`petrificus_totalus._registry.register_handler`) when it
    produces a different format - e.g. the docx handler renders to PDF, so
    ``report.docx`` becomes ``report.docx.pdf``. In that case, if this call
    is in place, the original file is removed once the new one is written
    successfully.

    Raises :class:`UnsupportedFileTypeError` if no handler is registered for
    the file's MIME type and it is not trusted.
    """
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    base_output = Path(output_path) if output_path is not None else input_path
    in_place = base_output == input_path
    mime_type = detect_mime_type(input_path)
    logger.debug(f"{input_path}: detected mime type: {mime_type}")

    trusted = trusted_mime_types is not None and mime_type.lower() in {
        t.lower() for t in trusted_mime_types
    }
    output_suffix: str | None
    if trusted:
        logger.debug(f"{input_path}: mime type is trusted, copying as-is")
        handler = shutil.copyfile
        output_suffix = None
    else:
        handler = get_handler(mime_type)
        if handler is None:
            raise UnsupportedFileTypeError(
                f"No CDR handler registered for MIME type {mime_type!r}"
            )
        logger.debug(f"{input_path}: will be handled by {handler.__module__}")
        output_suffix = get_output_suffix(mime_type)
    resolved_output = (
        base_output.with_name(base_output.name + output_suffix)
        if output_suffix
        and not base_output.name.lower().endswith(output_suffix.lower())
        else base_output
    )
    logger.debug(f"{input_path}: output will be {resolved_output}")

    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    # Handlers write to a temp path first, promoted via atomic rename only on
    # success. This matters most when output_path == input_path: a handler
    # that fails partway through must never leave a truncated file behind in
    # place of the original.
    tmp_output = resolved_output.with_name(f".{resolved_output.name}.disarming.tmp")
    logger.debug(f"{input_path}: temporary output: {tmp_output}")
    try:
        handler(input_path, tmp_output)
        os.replace(tmp_output, resolved_output)
    finally:
        tmp_output.unlink(missing_ok=True)

    if output_suffix and in_place:
        input_path.unlink()

    return resolved_output


def _disarm_worker(
    input_path: Path,
    output_path: Path,
    trusted_mime_types: Iterable[str] | None,
) -> DisarmResult:
    """Disarm one file, converting exceptions into a DisarmResult."""
    try:
        result_path = disarm_file(
            input_path, output_path, trusted_mime_types=trusted_mime_types
        )
    except UnsupportedFileTypeError as exc:
        return DisarmResult(input_path, None, "skipped", str(exc))
    except Exception as exc:  # noqa: BLE001
        return DisarmResult(input_path, None, "failed", f"{type(exc).__name__}: {exc}")
    return DisarmResult(input_path, result_path, "disarmed")


def disarm_folder(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    max_workers: int | None = None,
    trusted_mime_types: Iterable[str] | None = None,
) -> list[DisarmResult]:
    """Run content disarm & reconstruction on every file under ``input_dir``.

    Recurses through ``input_dir``, disarming each file in parallel across
    a process pool. Mirrors the input directory structure into ``output_dir`` if
    given, otherwise disarms files in place.

    Files with no registered handler are skipped (not copied through
    unsanitized) and reported with status "skipped". Per-file failures are
    reported with status "failed" rather than aborting the whole run.

    Files whose sniffed MIME type is in ``trusted_mime_types`` are copied
    through as-is instead - see :func:`disarm_file`.
    """
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)

    output_dir = input_dir if output_dir is None else Path(output_dir)

    results: list[DisarmResult] = []
    futures: list[concurrent.futures.Future[DisarmResult]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        for src in input_dir.rglob("*"):
            dst = output_dir / src.relative_to(input_dir)
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                continue

            if not src.is_file():
                continue

            futures.append(
                executor.submit(_disarm_worker, src, dst, trusted_mime_types)
            )

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result.status == "skipped":
                logger.warning(
                    f"Skipped unsupported file: {result.input_path} ({result.detail})"
                )
            elif result.status == "failed":
                logger.error(f"Failed to disarm {result.input_path} ({result.detail})")

            results.append(result)

    return results
