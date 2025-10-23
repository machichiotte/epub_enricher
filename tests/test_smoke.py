# tests/test_smoke.py
from __future__ import annotations

import os

import pytest  # pyright: ignore[reportMissingImports]


def test_import_package():
    import epub_enricher  # noqa: F401


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Tkinter GUI cannot run in headless CI environment",
)
def test_cli_entrypoint():
    from epub_enricher.__main__ import cli

    code = cli()
    assert isinstance(code, int)
    assert code == 0
