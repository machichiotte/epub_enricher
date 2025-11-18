# epub_enricher/src/epub_enricher/core/epub/cover_finder.py
"""
Module de recherche de couverture EPUB.

Responsabilité unique: Implémenter différentes stratégies pour trouver
la couverture d'un fichier EPUB.

Pattern: Strategy Pattern pour les différentes méthodes de recherche.
"""

import logging
from typing import Optional

from ebooklib import epub
from ebooklib.epub import EpubBook, EpubItem

logger = logging.getLogger(__name__)


def _find_cover_by_type(book: EpubBook) -> Optional[EpubItem]:
    """
    Stratégie 1: Chercher un item de type ITEM_COVER.

    Args:
        book: Objet EpubBook

    Returns:
        Item de couverture ou None
    """
    items = list(book.get_items_of_type(epub.ITEM_COVER))
    if items:
        logger.info("Cover found via ITEM_COVER")
        return items[0]
    return None


def _find_cover_by_opf(book: EpubBook) -> Optional[EpubItem]:
    """
    Stratégie 2: Chercher dans les métadonnées OPF.

    Args:
        book: Objet EpubBook

    Returns:
        Item de couverture ou None
    """
    meta_cover = book.get_metadata("OPF", "cover")
    if meta_cover:
        cover_id = meta_cover[0][1].get("content")
        if cover_id:
            logger.info("Cover found via OPF metadata")
            return book.get_item_with_id(cover_id)
    return None


def _find_cover_by_bruteforce(book: EpubBook) -> Optional[EpubItem]:
    """
    Stratégie 3: Recherche brute-force parmi les images.

    Cherche la première image dont le nom contient "cover" ou "couv",
    sinon retourne la première image disponible.

    Args:
        book: Objet EpubBook

    Returns:
        Item de couverture (meilleure estimation) ou None
    """
    logger.info("Standard cover methods failed. Trying brute-force...")
    images = list(book.get_items_of_type(epub.ITEM_IMAGE))
    if images:
        # Trier pour prioriser les images avec "cover" dans le nom
        images.sort(
            key=lambda x: (
                0 if "cover" in x.get_name().lower() else 1 if "couv" in x.get_name().lower() else 2
            )
        )
        logger.info("Cover found via brute-force: %s", images[0].get_name())
        return images[0]
    return None


def find_cover_data(book: EpubBook, epub_path: str) -> Optional[bytes]:
    """
    Tente d'extraire les données de la couverture en utilisant plusieurs stratégies.

    Cette fonction applique trois stratégies dans l'ordre:
    1. Recherche par type ITEM_COVER
    2. Recherche via métadonnées OPF
    3. Recherche brute-force parmi les images

    Args:
        book: Objet EpubBook
        epub_path: Chemin du fichier (pour logging uniquement)

    Returns:
        Données binaires de la couverture ou None si non trouvée
    """
    try:
        # Tentative avec les trois stratégies (fallback en cascade)
        cover_item = (
            _find_cover_by_type(book) or _find_cover_by_opf(book) or _find_cover_by_bruteforce(book)
        )

        if cover_item:
            logger.info("Cover image data extracted for %s", epub_path)
            return cover_item.get_content()

        logger.info("No cover found for %s", epub_path)

    except Exception:
        logger.warning("Could not extract cover image for %s", epub_path, exc_info=True)

    return None
