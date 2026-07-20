"""CDR handler for Word (.docx) and PowerPoint/Impress (.pptx, .odp) documents.

These formats can carry macros, embedded OLE objects, remote-template/DDE
injection, and other attack surface baked into their structure itself.
Stripping all of that while keeping the file genuinely editable would mean
enumerating every dangerous construct and trusting that enumeration is
complete. Since the goal here is safe *viewing* of an untrusted file rather
than re-editing it, this handler sidesteps that entirely: it renders the
document with LibreOffice (a real Word/PowerPoint-compatible layout engine,
so pagination and formatting come out faithfully, unlike a naive text dump)
and hands the resulting PDF to handlers/pdf.py's existing rasterize+OCR
pipeline -- the same "pixels only" CDR guarantee already used for PDFs and
images. The conversion step is format-agnostic (soffice --convert-to pdf),
so one handler covers all of them.

The output is therefore a PDF, not the original format (see the
output_suffix passed to register_handler): disarming "report.docx" in place
produces "report.docx.pdf", and the original is removed once that succeeds
(handled by core.disarm_file).
"""

import os
import subprocess
from pathlib import Path

from .._registry import register_handler
from ..helpers.tempfile import temp_dir
from .pdf import disarm as disarm_pdf

_CONVERT_TIMEOUT = 120


def disarm(input_path: Path, output_path: Path) -> None:
    with temp_dir(dirname=output_path, prefix=".disarming-") as tmp_dir:
        # Each conversion gets its own LibreOffice profile dir so concurrent
        # disarm_folder workers don't collide over the same profile lock.
        profile_dir = tmp_dir / "profile"
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_dir),
                f"-env:UserInstallation=file://{profile_dir}",
                str(input_path),
            ],
            check=True,
            capture_output=True,
            timeout=_CONVERT_TIMEOUT,
        )

        rendered_pdf = tmp_dir / f"{input_path.stem}.pdf"
        if not rendered_pdf.is_file():
            raise ValueError(f"LibreOffice did not produce a PDF for {input_path}")

        if os.getenv("PETRIFICUS_TRUST_LIBREOFFICE_PDF", False):
            rendered_pdf.rename(output_path)
        else:
            disarm_pdf(rendered_pdf, output_path)


register_handler(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.oasis.opendocument.text",
    "text/rtf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.presentation",
    output_suffix=".pdf",
)(disarm)
