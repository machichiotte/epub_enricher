from __future__ import annotations

import sys


def cli() -> int:
    try:
        # Import lazily so user can drop their epub_enricher.py later
        from .epub_enricher import main  # type: ignore
    except Exception as exc:  # pragma: no cover - startup error path
        sys.stderr.write(f"Failed to import epub_enricher.main: {exc}\n")
        return 1

    try:
        return int(bool(main())) * 0  # main may return None/Falsey; normalize to 0
    except SystemExit as se:  # pass through exit codes from main()
        return int(se.code) if isinstance(se.code, int) else 1
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"Unhandled error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())


