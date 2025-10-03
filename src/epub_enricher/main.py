# epub_enricher/src/epub_enricher/main.py
"""
Point d'entrée principal pour EPUB Enricher
Décide de lancer le GUI ou le CLI selon l'environnement
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from .config import (
    LOG_BACKUP_COUNT,
    LOG_DIR,
    LOG_ENCODING,
    LOG_MAX_BYTES,
    NO_GUI_ENV_VAR,
    ensure_directories,
)
from .gui.main_window import EnricherGUI


def setup_logging():
    """Configure le système de logging."""
    ensure_directories()
    logger = logging.getLogger("epub_enricher")
    logger.setLevel(logging.DEBUG)

    # Handler pour fichier avec rotation
    logfile = os.path.join(LOG_DIR, "epub_enricher.log")
    handler = RotatingFileHandler(
        logfile, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding=LOG_ENCODING
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Handler pour console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)

    return logger


def run_gui() -> int:
    """Lance l'interface graphique."""
    logger = logging.getLogger("epub_enricher")
    logger.info("Starting EPUB Enricher GUI")
    try:
        app = EnricherGUI()
        app.mainloop()
        return 0
    except Exception:
        logger.exception("Fatal error in main loop")
        return 1


def run_cli() -> int:
    """Lance le mode ligne de commande."""
    logger = logging.getLogger("epub_enricher")
    logger.info("Starting EPUB Enricher CLI mode")

    if len(sys.argv) < 2:
        print("Usage: python -m epub_enricher <folder_path> [--autosave]")
        print("  folder_path: Chemin vers le dossier contenant les fichiers EPUB")
        print("  --autosave: Applique automatiquement les suggestions")
        return 1

    folder_path = sys.argv[1]
    autosave = "--autosave" in sys.argv

    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory")
        return 1

    try:
        from .cli import cli_process_folder, print_metadata_summary

        metas = cli_process_folder(folder_path, autosave)
        print_metadata_summary(metas)
        return 0
    except Exception as e:
        logger.exception("Error in CLI mode")
        print(f"Error: {e}")
        return 1


def main() -> int:
    """Point d'entrée principal."""
    setup_logging()

    # Vérifier si on doit éviter le GUI
    if os.getenv(NO_GUI_ENV_VAR) == "1":
        logger = logging.getLogger("epub_enricher")
        logger.info("NO_GUI mode: running CLI")
        return run_cli()

    # Par défaut, lancer le GUI
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
