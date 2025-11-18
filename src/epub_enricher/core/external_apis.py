# epub_enricher/src/epub_enricher/core/external_apis.py
"""
Module de compatibilité rétroactive pour external_apis.

⚠️ DEPRECATED: Ce module est conservé uniquement pour la compatibilité
   rétroactive. Utilisez le nouveau module enrichment/ à la place:

   from epub_enricher.core.enrichment import fetch_enriched_metadata

Ce module sera supprimé dans une version future.
"""

import warnings

from .enrichment import (
    fetch_enriched_metadata,
    query_google_books,
    query_wikipedia_summary,
)
from .enrichment.genre_mapper import (
    GENRE_MAPPING,
    map_openlibrary_subject_to_genre,
)

# Alias pour compatibilité
fetch_genre_and_summary_from_sources = fetch_enriched_metadata

warnings.warn(
    "external_apis module is deprecated. "
    "Use 'from epub_enricher.core.enrichment import ...' instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "fetch_genre_and_summary_from_sources",
    "fetch_enriched_metadata",
    "query_google_books",
    "query_wikipedia_summary",
    "GENRE_MAPPING",
    "map_openlibrary_subject_to_genre",
]
