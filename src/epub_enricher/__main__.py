from __future__ import annotations

import os
import sys


def cli() -> int:
    try:
        from .main import main  # type: ignore
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"Failed to import epub_enricher.main: {exc}\n")
        return 1

    # Do not launch GUI in CI/headless if env is set
    if os.getenv("EPUB_ENRICHER_NO_GUI") == "1":
        try:
            return main()
        except SystemExit as se:  # pass through exit codes
            return int(se.code) if isinstance(se.code, int) else 1
        except Exception as exc:  # pragma: no cover
            sys.stderr.write(f"Unhandled error: {exc}\n")
            return 1

    try:
        code = main()
        return 0 if (code is None or code == 0) else int(code)
    except SystemExit as se:
        return int(se.code) if isinstance(se.code, int) else 1
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"Unhandled error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
