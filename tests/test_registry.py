from pathlib import Path

import pytest

from petrificus_totalus._registry import (
    _OUTPUT_SUFFIX,
    _REGISTRY,
    get_handler,
    get_output_suffix,
    register_handler,
)

_TEST_MIME = "application/x-petrificus-totalus-test"


@pytest.fixture(autouse=True)
def _cleanup_test_mime_type():
    yield
    _REGISTRY.pop(_TEST_MIME, None)
    _OUTPUT_SUFFIX.pop(_TEST_MIME, None)


def _noop_handler(input_path: Path, output_path: Path) -> None:
    pass


def test_register_handler_registers_and_dispatches():
    register_handler(_TEST_MIME)(_noop_handler)

    assert get_handler(_TEST_MIME) is _noop_handler


def test_register_handler_matches_mime_type_case_insensitively():
    register_handler(_TEST_MIME)(_noop_handler)

    assert get_handler(_TEST_MIME.upper()) is _noop_handler


def test_register_handler_rejects_duplicate_mime_type():
    register_handler(_TEST_MIME)(_noop_handler)

    with pytest.raises(ValueError, match="already registered"):
        register_handler(_TEST_MIME)(_noop_handler)


def test_get_output_suffix_defaults_to_none_when_unset():
    register_handler(_TEST_MIME)(_noop_handler)

    assert get_output_suffix(_TEST_MIME) is None


def test_get_output_suffix_returns_registered_suffix():
    register_handler(_TEST_MIME, output_suffix=".pdf")(_noop_handler)

    assert get_output_suffix(_TEST_MIME) == ".pdf"
