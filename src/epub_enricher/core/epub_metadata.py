# epub_enricher/src/epub_enricher/core/epub_metadata.py
"""
Module de compatibilité rétroactive pour epub_metadata.

⚠️ DEPRECATED: Ce module est conservé uniquement pour la compatibilité
   rétroactive. Utilisez le nouveau module epub/ à la place:

   from epub_enricher.core.epub import extract_metadata, update_epub_with_metadata

Ce module sera supprimé dans une version future.
"""

import warnings

# Imports depuis le nouveau module
from .epub import (
    extract_metadata,
    safe_read_epub,
    update_epub_with_metadata,
)

warnings.warn(
    "epub_metadata module is deprecated. Use 'from epub_enricher.core.epub import ...' instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "extract_metadata",
    "safe_read_epub",
    "update_epub_with_metadata",
]
