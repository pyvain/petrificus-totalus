"""CDR handler for Word (.docx) documents.

A .docx can carry macros, embedded OLE objects, remote-template/DDE
injection, and other attack surface baked into the OOXML structure itself.
Stripping all of that while keeping the file genuinely editable would mean
enumerating every dangerous construct and trusting that enumeration is
complete. Since the goal here is safe *viewing* of an untrusted file rather
than re-editing it, this handler sidesteps that entirely: it renders the
document with LibreOffice (a real Word-compatible layout engine, so
pagination and formatting come out faithfully, unlike a naive text dump) and
hands the resulting PDF to handlers/pdf.py's existing rasterize+OCR
pipeline -- the same "pixels only" CDR guarantee already used for PDFs and
images.

The output is therefore a PDF, not a .docx (see the output_suffix passed to
register_handler): disarming "report.docx" in place produces
"report.docx.pdf", and the original is removed once that succeeds (handled
by core.disarm_file).
"""

import subprocess
import tempfile
from pathlib import Path

from .._registry import register_handler
from .pdf import disarm as disarm_pdf

_CONVERT_TIMEOUT = 120


def disarm(input_path: Path, output_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Each conversion gets its own LibreOffice profile dir so concurrent
        # disarm_folder workers don't collide over the same profile lock.
        profile_dir = Path(tmp_dir) / "profile"
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp_dir,
                f"-env:UserInstallation=file://{profile_dir}",
                str(input_path),
            ],
            check=True,
            capture_output=True,
            timeout=_CONVERT_TIMEOUT,
        )

        rendered_pdf = Path(tmp_dir) / f"{input_path.stem}.pdf"
        if not rendered_pdf.is_file():
            raise ValueError(f"LibreOffice did not produce a PDF for {input_path}")

        disarm_pdf(rendered_pdf, output_path)


register_handler(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.oasis.opendocument.spreadsheet",
    output_suffix=".pdf",
)(disarm)
