"""CDR handlers, one module per file type.

To add support for a new file type, add a module here that decorates a
``petrify(input_path: Path, output_path: Path) -> None`` function with
``@register_handler(".ext1", ".ext2", ...)`` from
:mod:`petrificus_totalus._registry`. It will be discovered automatically --
no registration elsewhere is required.
"""
