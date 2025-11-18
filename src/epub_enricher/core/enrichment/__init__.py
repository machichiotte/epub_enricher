# epub_enricher/src/epub_enricher/core/enrichment/__init__.py
"""
Module Enrichment - Agrégation multi-sources pour enrichissement de métadonnées.

Ce module orchestre les appels à différentes API externes (Google Books,
Wikipedia, OpenLibrary) pour enrichir les métadonnées des EPUB avec des
informations complémentaires (résumé, genre, tags).
"""

# Exports publics
from .aggregator import fetch_enriched_metadata
from .google_books import query_google_books
from .wikipedia import query_wikipedia_summary

__all__ = [
    "fetch_enriched_metadata",
    "query_google_books",
    "query_wikipedia_summary",
]
