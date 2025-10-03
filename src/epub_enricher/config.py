# epub_enricher/src/epub_enricher/config.py
"""
Configuration et constantes pour EPUB Enricher
"""

import os
import re

# ---------- Configuration réseau ----------
API_TIMEOUT = 10
OPENLIB_SEARCH = "https://openlibrary.org/search.json"
OPENLIB_BOOK = "https://openlibrary.org/api/books"

# ---------- Dossiers ----------
COVER_CACHE_DIR = ".cover_cache"
BACKUP_DIR = "backups"
LOG_DIR = "logs"

# ---------- Extensions supportées ----------
SUPPORTED_EXT = (".epub",)

# ---------- Expressions régulières ----------
ISBN_RE = re.compile(r"(?:(?:ISBN(?:-1[03])?:?\s*)?)(97[89][ -]?)?[0-9][0-9 -]{8,}[0-9Xx]")

# ---------- Configuration retry/backoff ----------
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0
JITTER = 0.3  # fraction for jitter

# ---------- Configuration logging ----------
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 5
LOG_ENCODING = "utf-8"

# ---------- Configuration GUI ----------
GUI_TITLE = "EPUB Metadata Enricher"
GUI_GEOMETRY = "1100x700"
GUI_TREE_HEIGHT = 18
GUI_TEXT_HEIGHT = 8
GUI_COVER_SIZE = (200, 300)

# ---------- Variables d'environnement ----------
NO_GUI_ENV_VAR = "EPUB_ENRICHER_NO_GUI"


# ---------- Initialisation des dossiers ----------
def ensure_directories():
    """Crée les dossiers nécessaires s'ils n'existent pas."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
