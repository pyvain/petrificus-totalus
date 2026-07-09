"""Command-line interface: ``petrificus-totalus`` disarms a single file or a folder."""

import argparse
import logging
import sys
from pathlib import Path

from ._registry import detect_mime_type
from .core import DisarmResult, UnsupportedFileTypeError, disarm_file, disarm_folder


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="petrificus-totalus",
        description="Content disarm & reconstruction (CDR) for a single file or a folder.",
    )
    parser.add_argument("input", type=Path, help="File or directory to disarm.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file or directory. Defaults to disarming in place.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Max worker processes when disarming a folder (default: CPU count).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    return parser


def _print_folder_summary(results: list[DisarmResult]) -> int:
    counts = {"disarmed": 0, "skipped": 0, "failed": 0}
    for result in sorted(results, key=lambda r: r.input_path):
        counts[result.status] += 1
        # if result.status == "failed":
        #    print(f"FAILED   {result.input_path}: {result.detail}", file=sys.stderr)
    print(
        f"{counts['disarmed']} disarmed, {counts['skipped']} skipped, {counts['failed']} failed"
    )
    return 1 if counts["failed"] else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    logger = logging.getLogger("petrificus-totalus")
    # logger.addHandler(logging.StreamHandler())

    if args.input.is_dir():
        try:
            results = disarm_folder(
                args.input, args.output, max_workers=args.max_workers
            )
        except NotADirectoryError as exc:
            print(f"petrificus-totalus: not a directory: {exc}", file=sys.stderr)
            return 1
        return _print_folder_summary(results)

    try:
        output_path = disarm_file(args.input, args.output)
    except FileNotFoundError:
        print(f"petrificus-totalus: no such file: {args.input}", file=sys.stderr)
        return 1
    except UnsupportedFileTypeError as exc:
        print(f"petrificus-totalus: {exc}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
