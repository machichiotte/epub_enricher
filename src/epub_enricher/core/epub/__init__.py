# epub_enricher/src/epub_enricher/core/epub/__init__.py
"""
Module EPUB - Gestion complète des fichiers EPUB.

Ce module fournit des fonctions pour lire et écrire les métadonnées
des fichiers EPUB en respectant la séparation des responsabilités.
"""

# Exports publics pour compatibilité rétroactive
from .reader import extract_metadata, safe_read_epub
from .writer import update_epub_with_metadata

__all__ = [
    "extract_metadata",
    "safe_read_epub",
    "update_epub_with_metadata",
]
