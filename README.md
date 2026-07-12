# petrificus-totalus

An open-source content disarm & reconstruction (CDR) library. 

# Goals

Rewrite untrusted and potentially unsafe files into versions that cannot
reasonably exploit a reader for that file type. Feel free to open issues
to discuss the subjective choices I made.

This library aims at preserving the file type (e.g. disarming a JPEG image
outputs a JPEG image).

As a temporary implementation, when CDR is deemed too complex to exhaustively
remove potentially unsafe file elements, a safe PDF equivalent of the file
is built instead. The goal is to provide safe file viewing by accepting to
lose the capability to edit the file in its original format (e.g. for now,
disarming a `.docx` file outputs a `.docx.pdf` safe equivalent)

The disarming method for a file is chosen from its MIME type rather than
its file name extension, so a malicious payload can't dodge disarming just
by being renamed `photo.jpg`.

> [!CAUTION]
>  **This library does not provide isolation.**
>
> The file readers and libraries used to parse untrusted input (image codecs,
> PDF/Office renderers, OCR) can themselves be exploited, and a malicious file
> could compromise the system before disarming ever completes. Always run
> petrificus-totalus inside an isolated environment, such as a VM or (less
> secure) container - never directly on a machine you care about.
>
> For a ready-made isolation setup, see Freedom of the Press Foundation's
> [Dangerzone](https://github.com/freedomofpress/dangerzone) project, which
> converts everything to safe PDFs.
>
> Built-in isolation may be added to this project in the future.

## Usage

```python
from petrificus_totalus import disarm_file, disarm_folder

# Single file, overwritten in place.
disarm_file("suspicious.jpg")

# Single file, written to a new path (original left untouched).
disarm_file("suspicious.jpg", "clean/suspicious.jpg")

# Whole directory tree, processed in parallel, mirrored into output_dir.
results = disarm_folder("untrusted/", "clean/")
for r in results:
    print(r.input_path, r.status)  # "disarmed", "trusted", "skipped", or "failed"
```

Files with no registered handler are **skipped**, not copied through
unsanitized - they are reported with status `"skipped"` in the returned
`disarmResult` list rather than appearing in the output. Per-file failures
are reported as `"failed"` rather than aborting the whole `disarm_folder()`
run.

`disarm_folder()` processes files in parallel using a `ProcessPoolExecutor`
(pass `max_workers=` to control concurrency). Process-based isolation means a
crash triggered by a malformed or malicious input only takes down that one
file's worker, not the whole run.

Both functions accept `trusted_mime_types=`, an iterable of MIME types to
copy through as-is instead of disarming:

```python
disarm_file("photo.jpg", trusted_mime_types=["image/jpeg"])
disarm_folder("untrusted/", "clean/", trusted_mime_types=["image/jpeg", "application/pdf"])
```

## Command line

```bash
petrificus-totalus suspicious.jpg               # disarm in place
petrificus-totalus suspicious.jpg -o clean.jpg  # disarm to a new path
petrificus-totalus untrusted/ -o clean/         # disarm a whole directory tree
petrificus-totalus untrusted/ --max-workers 4   # cap worker processes
petrificus-totalus untrusted/ --trust-mime image/jpeg --trust-mime application/pdf
```

Disarming a single file prints the output path on success. disarming a
directory prints one summary line (counts of petrified/skipped/failed) and
exits non-zero if any file failed.

`--trust-mime` copies files whose sniffed MIME type matches through as-is
instead of disarming them; pass it multiple times to trust several MIME
types.

## Supported file types

| Type | Strategy |
|---|---|
| JPEG, PNG, BMP |  Fully decode, then re-encode through a different intermediate codec before saving back to the original format. |
| PDF | Rasterize every page to a bitmap and rebuild a fresh PDF from pixels alone, then run OCR (auto-detected language) to restore a searchable text layer. |
| MS Word, LibreOffice Writer | Render with LibreOffice to PDF, then run the PDF strategy above. Output is `<name>.docx.pdf` or `<name>.odt.pdf`, not a `.docx` or a `.odt` |
| MS Excel, LibreOffice Calc | Render with LibreOffice to PDF, widening each sheet's page to fit its used columns so none spill onto a separate page, then run the PDF strategy above. Output is `<name>.xlsx.pdf` or `<name>.ods.pdf`, not a `.xlsx` or a `.ods` |
| MS PowerPoint, LibreOffice Impress | Render with LibreOffice to PDF, then run the PDF strategy above. Output is `<name>.pptx.pdf` or `<name>.odp.pdf`, not a `.pptx` or a `.odp` |
| Plain text, CSV | Copy unmodified. |

Files are matched by MIME type, not extension - see `iter_supported_mime_types()`.

## Adding a new file type

Add a module to `src/petrificus_totalus/handlers/` that registers a
`disarm(input_path: Path, output_path: Path) -> None` function against one
or more MIME types (matched from content, not extension - see
`_registry.detect_mime_type`):

```python
# src/petrificus_totalus/handlers/example.py
from pathlib import Path
from .._registry import register_handler

def disarm(input_path: Path, output_path: Path) -> None:
    ...  # write a disarmed version of input_path to output_path

register_handler("application/x-example")(disarm)
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

## External dependencies

The project uses the following external dependencies not installed by `uv
sync`:
* LibreOffice (`soffice`, for `.docx` rendering)
* Tesseract (OCR, via `ocrmypdf`).
