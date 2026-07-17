"""Temporary files and directories rooted at a caller-chosen directory.

:mod:`tempfile` defaults to a location like ``/tmp``, which is often a
RAM-backed tmpfs and, more importantly, is frequently a different
filesystem than wherever the caller ultimately wants to write its output.
That matters for two reasons: large scratch data (rasterized pages, video
frames) can exhaust RAM instead of disk, and a temp resource can't be
promoted to a permanent one with a plain :meth:`~pathlib.Path.rename` once
it's done, since rename can't cross filesystems. These context managers
create the temp resource inside a given directory (typically the same
directory as the eventual output) instead, so it's on the same filesystem
and a same-filesystem rename is always available.

On exit, if the temp path is still where it was created, it's removed
(recursively, for directories); if it's already been renamed elsewhere --
i.e. promoted to a permanent result -- it's left alone. This runs whether
the body completed normally or raised, so a failure partway through never
leaves scratch state behind.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def temp_dir(
    prefix: str = ".tmp-",
    *,
    parent_dir: str | Path | None = None,
    dirname: str | Path | None = None,
) -> Iterator[Path]:
    """Yield a fresh empty directory.

    By default, the directory is created inside ``parent_dir`` with a randomized
    name: ``prefix`` plus a random string, per :func:`tempfile.mkdtemp`.

    When ``dirname`` is provided instead of ``parent_dir``, the ``parent_dir``
    defaults to ``dirname``'s parent directory, and the prefix becomes
    ``{prefix}{dirname.name}``.

    Promote it to a permanent result with ``path.rename(destination)``
    before the ``with`` block ends. Otherwise, it (and everything written
    into it) is deleted when the block exits -- including on error.
    """
    if parent_dir is not None and dirname is None:
        parent_dir = Path(parent_dir)
    elif parent_dir is None and dirname is not None:
        dirname = Path(dirname)
        parent_dir = dirname.parent
        prefix = f"{prefix}{dirname.name}"
    else:
        raise ValueError("temp_file() requires one of 'parent_dir' or 'dirname'")

    parent_dir.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=parent_dir, prefix=prefix))

    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


@contextmanager
def temp_file(
    prefix: str = ".tmp-",
    suffix: str = "",
    *,
    parent_dir: str | Path | None = None,
    filename: str | Path | None = None,
) -> Iterator[Path]:
    """Yield a path to a fresh empty file.

    By default, the file is created inside ``parent_dir`` with a randomized name:
    ``prefix`` plus a random string plus ``suffix``, per
    :func:`tempfile.mkstemp`.

    When ``filename`` is provided instead of ``parent_dir``, the ``parent_dir``
    defaults to ``filename``'s parent directory, and the prefix becomes
    ``{prefix}{filename.name}``.

    Promote it to a permanent result with ``path.rename(destination)``
    before the ``with`` block ends. Otherwise, it is deleted when the block
    exits -- including on error.
    """
    if parent_dir is not None and filename is None:
        parent_dir = Path(parent_dir)
    elif parent_dir is None and filename is not None:
        filename = Path(filename)
        parent_dir = filename.parent
        prefix = f"{prefix}{filename.name}"
    else:
        raise ValueError("temp_file() requires one of 'parent_dir' or 'filename'")

    parent_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=parent_dir, prefix=prefix, suffix=suffix)
    os.close(fd)
    tmp_name = Path(tmp_name)

    try:
        yield tmp_name
    finally:
        tmp_name.unlink(missing_ok=True)
