# epub_enricher/src/epub_enricher/cli.py
"""
Logique pour le mode ligne de commande.

Utilise EnricherService pour réutiliser la logique d'enrichissement.
"""

import logging
from typing import List

from .core.enricher_service import EnricherService
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
    logger.info(f"CLI mode - processing folder: {folder}")
    
    # Utiliser le service pour traiter le dossier
    service = EnricherService()
    metas = service.process_folder(folder, autosave=autosave)
    
    logger.info(f"CLI mode - processed {len(metas)} files")
    return metas


def print_metadata_summary(metas: List[EpubMeta]):
    """Affiche un résumé des métadonnées traitées."""
    print("\n=== Résumé du traitement ===")
    print(f"Fichiers traités: {len(metas)}")

    with_suggestions = sum(1 for m in metas if m.processed)
    print(f"Avec suggestions: {with_suggestions}")

    if with_suggestions > 0:
        print("\n=== Fichiers avec suggestions ===")
        for meta in metas:
            if not meta.processed:
                continue
                
            print(f"\n{meta.filename}:")
            
            # Comparer et afficher les changements
            if meta.original_title != meta.suggested_title:
                print(f"  Titre: {meta.original_title} -> {meta.suggested_title}")
                
            if meta.original_authors != meta.suggested_authors:
                print(f"  Auteurs: {meta.original_authors} -> {meta.suggested_authors}")
                
            if meta.original_isbn != meta.suggested_isbn:
                print(f"  ISBN: {meta.original_isbn} -> {meta.suggested_isbn}")
                
            if meta.original_language != meta.suggested_language:
                print(f"  Langue: {meta.original_language} -> {meta.suggested_language}")
                
            if meta.original_publisher != meta.suggested_publisher:
                print(f"  Éditeur: {meta.original_publisher} -> {meta.suggested_publisher}")
                
            if meta.original_publication_date != meta.suggested_publication_date:
                print(
                    f"  Date: {meta.original_publication_date} -> "
                    f"{meta.suggested_publication_date}"
                )
                
            if meta.original_tags != meta.suggested_tags:
                orig_tags = ", ".join(meta.original_tags or [])
                sugg_tags = ", ".join(meta.suggested_tags or [])
                print(f"  Tags: {orig_tags} -> {sugg_tags}")
                
            if meta.original_summary != meta.suggested_summary:
                orig_summary = (meta.original_summary or "")[:50] + "..."
                sugg_summary = (meta.suggested_summary or "")[:50] + "..."
                print(f"  Résumé: {orig_summary} -> {sugg_summary}")
                
            if meta.suggested_cover_data and meta.suggested_cover_data != meta.original_cover_data:
                print("  Couverture: Nouvelle couverture disponible")

