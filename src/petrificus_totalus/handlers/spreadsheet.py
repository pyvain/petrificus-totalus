"""CDR handler for spreadsheet (.xlsx, .xls, .ods) documents.

The output is a PDF, not the original spreadsheet format: disarming
"report.xlsx" in place produces "report.xlsx.pdf".
"""

import os
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path

from .._registry import register_handler
from ..helpers.tempfile import temp_dir
from .pdf import disarm as disarm_pdf

_CONVERT_TIMEOUT = 120
_SOFFICE_SHUTDOWN_TIMEOUT = 30


# Using ``--convert-to pdf`` with soffice paginates each sheet across a fixed
# page size, which splits wide sheets so that some columns land on separate pages
# from their neighbors. To avoid that, this handler drives LibreOffice over UNO,
# using the helpers/spreadsheet_script.py script to widen each sheet's page to
# fit its used columns before exporting, so every column always comes out on the
# same page.

# The UNO Python bridge lives in the system LibreOffice install, not in this
# project's venv, so that script is run as a subprocess under the system
# interpreter rather than imported here.
_UNO_SCRIPT = Path(__file__).resolve().parents[1] / "helpers" / "spreadsheet_script.py"
_UNO_PYTHON = "/usr/bin/python3"


def disarm(input_path: Path, output_path: Path) -> None:
    with temp_dir(dirname=output_path, prefix=".disarming-") as tmp_dir:
        profile = tmp_dir / "profile"
        pipe = f"petrificus_totalus_{uuid.uuid4().hex}"

        soffice = subprocess.Popen(
            [
                "soffice",
                "--headless",
                "--invisible",
                "--nologo",
                "--norestore",
                f"-env:UserInstallation=file://{profile}",
                f"--accept=pipe,name={pipe};urp;",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            subprocess.run(
                [
                    _UNO_PYTHON,
                    str(_UNO_SCRIPT),
                    pipe,
                    str(input_path),
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                timeout=_CONVERT_TIMEOUT,
            )
        finally:
            soffice.terminate()
            try:
                soffice.wait(timeout=_SOFFICE_SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                soffice.kill()
                soffice.wait()

        if not output_path.is_file():
            raise ValueError(f"LibreOffice did not produce a PDF for {input_path}")

        if not os.getenv("PETRIFICUS_TRUST_LIBREOFFICE_PDF", False):
            disarm_pdf(output_path, output_path)


register_handler(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.oasis.opendocument.spreadsheet",
    output_suffix=".pdf",
)(disarm)
