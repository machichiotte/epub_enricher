# epub_enricher/src/epub_enricher/cli.py
"""
Logique pour le mode ligne de commande
"""

import logging
import os
from typing import List

from .core.epub_processor import extract_metadata, find_epubs_in_folder, update_epub_with_metadata
from .core.metadata_fetcher import download_cover, extract_suggested_from_openlib
from .core.models import EpubMeta

logger = logging.getLogger(__name__)


def cli_process_folder(folder: str, autosave: bool = False) -> List[EpubMeta]:
    """
    Traite un dossier entier en mode CLI.

    Args:
        folder: Chemin vers le dossier contenant les EPUBs
        autosave: Si True, applique automatiquement les suggestions

    Returns:
        Liste des métadonnées traitées
    """
    files = find_epubs_in_folder(folder)
    metas = []

    for p in files:
        # Extraire les métadonnées originales
        res = extract_metadata(p)
        em = EpubMeta(
            path=p,
            filename=os.path.basename(p),
            original_title=res.get("title"),
            original_authors=res.get("authors"),
            original_isbn=res.get("identifier"),
            original_language=res.get("language"),
        )

        # Récupérer les suggestions
        suggested = extract_suggested_from_openlib(
            em.original_isbn, em.original_title, em.original_authors
        )
        em.suggested_title = suggested.get("title") or em.original_title
        em.suggested_authors = suggested.get("authors") or em.original_authors
        em.suggested_isbn = suggested.get("isbn") or em.original_isbn
        em.suggested_language = suggested.get("language") or em.original_language
        em.suggested_cover_url = suggested.get("cover")

        metas.append(em)
        logger.info("Prepared suggestion for: %s", em.filename)

        # Appliquer automatiquement si demandé
        if autosave and em.suggested_title:
            update_epub_with_metadata(p, em, download_cover)

    return metas


def print_metadata_summary(metas: List[EpubMeta]):
    """Affiche un résumé des métadonnées traitées."""
    print("\n=== Résumé du traitement ===")
    print(f"Fichiers traités: {len(metas)}")

    with_suggestions = sum(1 for m in metas if m.suggested_title)
    print(f"Avec suggestions: {with_suggestions}")

    if with_suggestions > 0:
        print("\n=== Fichiers avec suggestions ===")
        for meta in metas:
            if meta.suggested_title:
                print(f"\n{meta.filename}:")
                if meta.original_title != meta.suggested_title:
                    print(f"  Titre: {meta.original_title} -> {meta.suggested_title}")
                if meta.original_authors != meta.suggested_authors:
                    print(f"  Auteurs: {meta.original_authors} -> {meta.suggested_authors}")
                if meta.original_isbn != meta.suggested_isbn:
                    print(f"  ISBN: {meta.original_isbn} -> {meta.suggested_isbn}")
                if meta.original_language != meta.suggested_language:
                    print(f"  Langue: {meta.original_language} -> {meta.suggested_language}")
                if meta.suggested_cover_url:
                    print(f"  Couverture: {meta.suggested_cover_url}")
