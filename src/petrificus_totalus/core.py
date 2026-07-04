"""Core CDR orchestration: :func:`petrify_file` and :func:`petrify_folder`."""

import concurrent.futures
import dataclasses
import logging
import os
from pathlib import Path
from typing import Literal

from ._registry import detect_mime_type, get_handler, get_output_suffix

logger = logging.getLogger("petrificus_totalus")


class UnsupportedFileTypeError(Exception):
    """Raised when no CDR handler is registered for a file's MIME type."""


@dataclasses.dataclass(frozen=True)
class PetrifyResult:
    """Outcome of petrifying a single file within a :func:`petrify_folder` run."""

    input_path: Path
    output_path: Path | None
    status: Literal["petrified", "skipped", "failed"]
    detail: str | None = None


def petrify_file(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Run content disarm & reconstruction on a single file.

    Dispatches to the handler registered for the MIME type sniffed from
    ``input_path``'s actual content (not its extension), which rewrites it
    into a version that cannot reasonably exploit a reader for that file
    type. Writes to ``output_path`` if given, otherwise overwrites
    ``input_path`` in place.

    Most handlers preserve the input's format, so the output has the same
    extension. A handler may instead be registered with an ``output_suffix``
    (see :func:`petrificus_totalus._registry.register_handler`) when it
    produces a different format -- e.g. the docx handler renders to PDF, so
    ``report.docx`` becomes ``report.docx.pdf``. In that case, if this call
    is in place (no separate ``output_path`` was requested), the original
    file is removed once the new one is written successfully: nothing
    untrusted should be left behind just because the safe form has a
    different extension.

    Raises :class:`UnsupportedFileTypeError` if no handler is registered for
    the file's MIME type.
    """
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    base_output = Path(output_path) if output_path is not None else input_path
    in_place = base_output == input_path
    mime_type = detect_mime_type(input_path)
    handler = get_handler(mime_type)
    if handler is None:
        raise UnsupportedFileTypeError(
            f"No CDR handler registered for MIME type {mime_type!r}"
        )

    output_suffix = get_output_suffix(mime_type)
    resolved_output = (
        base_output.with_name(base_output.name + output_suffix) if output_suffix else base_output
    )

    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    # Handlers write to a temp path first, promoted via atomic rename only on
    # success. This matters most when output_path == input_path: a handler
    # that fails partway through must never leave a truncated file behind in
    # place of the original.
    tmp_output = resolved_output.with_name(f".{resolved_output.name}.petrifying.tmp")
    try:
        handler(input_path, tmp_output)
        os.replace(tmp_output, resolved_output)
    finally:
        tmp_output.unlink(missing_ok=True)

    if output_suffix and in_place:
        input_path.unlink()

    return resolved_output


def _petrify_worker(input_path: Path, output_path: Path) -> PetrifyResult:
    """Petrify one file, converting exceptions into a PetrifyResult.

    Runs inside a worker process. Isolating each file's handler in its own
    process means a crash or hang triggered by a malicious/malformed input
    only takes down that one job, not the whole petrify_folder() run.
    """
    try:
        result_path = petrify_file(input_path, output_path)
    except UnsupportedFileTypeError as exc:
        return PetrifyResult(input_path, None, "skipped", str(exc))
    except Exception as exc:  # noqa: BLE001 - deliberately isolate worker failures
        return PetrifyResult(input_path, None, "failed", f"{type(exc).__name__}: {exc}")
    return PetrifyResult(input_path, result_path, "petrified")


def petrify_folder(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    max_workers: int | None = None,
) -> list[PetrifyResult]:
    """Run content disarm & reconstruction on every file under ``input_dir``.

    Recurses through ``input_dir``, petrifying each file in parallel across
    a process pool (see :func:`_petrify_worker` for why processes rather than
    threads). Mirrors the input directory structure into ``output_dir`` if
    given, otherwise petrifies files in place.

    Files with no registered handler are skipped (not copied through
    unsanitized) and reported with status "skipped". Per-file failures are
    reported with status "failed" rather than aborting the whole run.
    """
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)

    in_place = output_dir is None
    resolved_output_dir = input_dir if in_place else Path(output_dir)

    jobs = []
    for src in input_dir.rglob("*"):
        if not src.is_file():
            continue
        dst = src if in_place else resolved_output_dir / src.relative_to(input_dir)
        jobs.append((src, dst))

    results: list[PetrifyResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_petrify_worker, src, dst): src for src, dst in jobs}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    for result in results:
        if result.status == "skipped":
            logger.warning("Skipped unsupported file: %s (%s)", result.input_path, result.detail)
        elif result.status == "failed":
            logger.error("Failed to petrify %s: %s", result.input_path, result.detail)

    return results
