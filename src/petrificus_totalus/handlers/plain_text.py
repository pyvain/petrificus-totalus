"""CDR handler for Word (.docx) documents.

Plain text files are not considered dangerous and can be kept as they are
"""

import shutil
from pathlib import Path

from .._registry import register_handler


def disarm(input_path: Path, output_path: Path) -> None:
    if output_path != input_path:
        shutil.copy(input_path, output_path)


register_handler("text/plain", "text/csv")(disarm)
