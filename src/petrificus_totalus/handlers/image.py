"""CDR handler for raster images: JPEG, PNG, BMP.

Disarms by fully decoding the image and re-encoding it through a different
intermediate codec before saving back to the original format. This forces
the image library to reconstruct the file from actual pixel data alone,
discarding anything that isn't pixel data -- malformed chunks, polyglot
payloads, embedded objects/scripts -- rather than copying bytes through.
"""

import io
from pathlib import Path

from PIL import Image

from .._registry import register_handler


def petrify(input_path: Path, output_path: Path) -> None:
    with Image.open(input_path) as original:
        original.load()
        # Trust Pillow's own content-sniffed format, not the file extension.
        save_format = original.format
        # WEBP (lossless) is used as the intermediate for PNG since it preserves
        # an alpha channel; PNG is used for the rest since none of them carry
        # alpha in a way that would be lost re-encoding through it.
        intermediate_format = "WEBP" if save_format == "PNG" else "PNG"
        intermediate_kwargs = {"lossless": True} if intermediate_format == "WEBP" else {}

        buffer = io.BytesIO()
        original.save(buffer, format=intermediate_format, **intermediate_kwargs)

    buffer.seek(0)
    with Image.open(buffer) as roundtripped:
        roundtripped.load()
        if save_format == "JPEG" and roundtripped.mode != "RGB":
            roundtripped = roundtripped.convert("RGB")
        roundtripped.save(output_path, format=save_format)


register_handler("image/jpeg", "image/png", "image/bmp", "image/x-ms-bmp")(petrify)
