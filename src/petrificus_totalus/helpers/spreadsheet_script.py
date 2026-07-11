"""
Use LibreOffice's Python-UNO bridge to widen each sheet's page to its used
column width, then exports to PDF.
"""

import os
import sys
import time

# ``uno`` only exists in the system LibreOffice install, not in this project's
# venv, so the spreadsheet handler runs this script as a subprocess under the system's
# python interpreter rather than importing it directly.
import uno  # pyright: ignore[reportMissingImports]
from com.sun.star.beans import PropertyValue  # pyright: ignore[reportMissingImports]

CONNECT_RETRIES = 60
CONNECT_RETRY_DELAY = 0.5

# UNO reports column widths in 1/100 mm, but Calc's page layout engine
# quantizes each column to twips (1/1440 in) independently when it renders
# the page. Summing the raw 1/100 mm widths and converting once loses up to
# a twip per column to rounding, so a wide-enough sheet's last column can
# spill onto its own page even though the sums "match" in 1/100 mm.
_MM100_PER_TWIP = 2540
_TWIPS_PER_INCH = 1440


def mm100_to_twips_ceil(mm100):
    return -(-mm100 * _TWIPS_PER_INCH // _MM100_PER_TWIP)


def twips_to_mm100_ceil(twips):
    return -(-twips * _MM100_PER_TWIP // _TWIPS_PER_INCH)


def used_width(sheet, end_col):
    total_twips = sum(
        mm100_to_twips_ceil(sheet.Columns.getByIndex(c).Width)
        for c in range(end_col + 1)
    )
    return twips_to_mm100_ceil(total_twips)


def connect(pipe_name):
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    url = f"uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext"
    last_exc = None
    for _ in range(CONNECT_RETRIES):
        try:
            return resolver.resolve(url)
        except Exception as exc:  # noqa: BLE001 - retrying until soffice is up
            last_exc = exc
            time.sleep(CONNECT_RETRY_DELAY)
    raise RuntimeError(
        f"could not connect to soffice on pipe {pipe_name!r}"
    ) from last_exc


def prop(name, value):
    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def widen_sheet_to_content(doc, page_styles, sheet, index):
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(False)
    width = used_width(sheet, cursor.RangeAddress.EndColumn)

    style_name = f"PetrificusFitWidth{index}"
    if not page_styles.hasByName(style_name):
        page_styles.insertByName(
            style_name, doc.createInstance("com.sun.star.style.PageStyle")
        )
    style = page_styles.getByName(style_name)

    # No scaling
    style.ScaleToPages = 0
    style.ScaleToPagesX = 0
    style.ScaleToPagesY = 0
    style.PageScale = 100
    style.Width = width + style.LeftMargin + style.RightMargin

    sheet.PageStyle = style_name


def pilot_soffice(pipe_name: str, input_path: str, output_path: str):
    remote_ctx = connect(pipe_name)
    desktop = remote_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", remote_ctx
    )

    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(os.path.abspath(input_path)),
        "_blank",
        0,
        (prop("Hidden", True),),
    )
    assert (
        doc is not None
    ), f"Can't open document {input_path}. Is it open by another program?"
    try:
        page_styles = doc.StyleFamilies.getByName("PageStyles")
        for i in range(doc.Sheets.Count):
            widen_sheet_to_content(doc, page_styles, doc.Sheets.getByIndex(i), i)

        doc.storeToURL(
            uno.systemPathToFileUrl(os.path.abspath(output_path)),
            (prop("FilterName", "calc_pdf_Export"),),
        )
    finally:
        doc.close(False)


def main():
    if len(sys.argv) != 4:
        print(
            f"Usage: {sys.argv[0]} <pipe name> <input spreadsheet> <output pdf>",
            file=sys.stderr,
        )
        exit(1)

    pipe_name = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3]

    pilot_soffice(pipe_name, input_path, output_path)


if __name__ == "__main__":
    main()
