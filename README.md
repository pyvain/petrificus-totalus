# petrificus-totalus

A modular content disarm & reconstruction (CDR) library. It rewrites
untrusted files into versions that cannot reasonably exploit a reader for
that file type, preserving the original file type wherever possible (e.g. a
`.jpg` in, a `.jpg` out).

The handler for a file is chosen from its actual content (sniffed via
`libmagic`), never its name or extension, so a malicious payload can't dodge
disarming just by being renamed `photo.jpg`.

## Usage

```python
from petrificus_totalus import petrify_file, petrify_folder

# Single file, overwritten in place.
petrify_file("suspicious.jpg")

# Single file, written to a new path (original left untouched).
petrify_file("suspicious.jpg", "clean/suspicious.jpg")

# Whole directory tree, processed in parallel, mirrored into output_dir.
results = petrify_folder("untrusted/", "clean/")
for r in results:
    print(r.input_path, r.status)  # "petrified", "skipped", or "failed"
```

Files with no registered handler are **skipped**, not copied through
unsanitized - they're reported with status `"skipped"` in the returned
`PetrifyResult` list rather than appearing in the output. Per-file failures
are reported as `"failed"` rather than aborting the whole `petrify_folder()`
run.

`petrify_folder()` processes files in parallel using a `ProcessPoolExecutor`
(pass `max_workers=` to control concurrency). Process-based isolation means a
crash triggered by a malformed or malicious input only takes down that one
file's worker, not the whole run.

## Command line

```bash
petrificus-totalus suspicious.jpg              # petrify in place
petrificus-totalus suspicious.jpg -o clean.jpg  # petrify to a new path
petrificus-totalus untrusted/ -o clean/         # petrify a whole directory tree
petrificus-totalus untrusted/ --max-workers 4   # cap worker processes
```

Petrifying a single file prints the output path on success. Petrifying a
directory prints one summary line (counts of petrified/skipped/failed) and
exits non-zero if any file failed.

## Supported file types

| Type | Extensions | Strategy |
|---|---|---|
| Images | `.jpg`, `.jpeg`, `.png`, `.bmp` | Fully decode, then re-encode through a different intermediate codec before saving back to the original format. |
| PDF | `.pdf` | Rasterize every page to a bitmap and rebuild a fresh PDF from pixels alone, then run OCR (auto-detected language) to restore a searchable text layer. |
| Word | `.docx` | Render with LibreOffice to PDF, then run the PDF strategy above. Output is `<name>.docx.pdf`, not a `.docx` - the original is removed once petrifying succeeds. |

Files are matched by MIME type, not extension - see `iter_supported_mime_types()`.

## Adding a new file type

Add a module to `src/petrificus_totalus/handlers/` that registers a
`petrify(input_path: Path, output_path: Path) -> None` function against one
or more MIME types (matched from content, not extension - see
`_registry.detect_mime_type`):

```python
# src/petrificus_totalus/handlers/example.py
from pathlib import Path
from .._registry import register_handler

def petrify(input_path: Path, output_path: Path) -> None:
    ...  # write a disarmed version of input_path to output_path

register_handler("application/x-example")(petrify)
```

It's discovered automatically - no other registration is required. Pass
`output_suffix=".ext"` to `register_handler()` if the handler produces a
different format than it received (like the Word handler producing a PDF)
rather than preserving the input's extension.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # install dependencies
uv run pytest      # run tests
uv build           # build a wheel + sdist into dist/
```

The PDF and Word handlers also need system binaries not installed by `uv
sync`: `libmagic` (MIME sniffing), LibreOffice (`soffice`, for `.docx`
rendering), and Tesseract (OCR, via `ocrmypdf`).
