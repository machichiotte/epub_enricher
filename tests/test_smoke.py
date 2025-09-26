from __future__ import annotations


def test_import_package():
    import epub_enricher  # noqa: F401


def test_cli_entrypoint():
    from epub_enricher.__main__ import cli

    code = cli()
    assert isinstance(code, int)
    assert code == 0


