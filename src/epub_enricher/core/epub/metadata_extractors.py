# epub_enricher/src/epub_enricher/core/epub/metadata_extractors.py
"""
Module d'extracteurs de métadonnées avancés.

Responsabilité unique: Fournir des extracteurs spécialisés pour
les métadonnées difficiles à obtenir (langue, ISBN depuis le texte).
"""

import logging
import re
from typing import Optional

from ebooklib import epub
from ebooklib.epub import EpubBook
from isbnlib import canonical, is_isbn10, is_isbn13

logger = logging.getLogger(__name__)


def detect_language_from_text(book: EpubBook) -> Optional[str]:
    """
    Détecte la langue du livre depuis son contenu textuel.

    Fallback utilisé quand la métadonnée DC language est absente.
    Analyse les 3000 premiers caractères du premier document.

    Args:
        book: Objet EpubBook

    Returns:
        Code de langue (ex: 'fr', 'en') ou None si échec
    """
    try:
        from langdetect import detect

        docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
        if docs:
            # Prendre le premier document
            text = docs[0].get_content().decode("utf-8", errors="ignore")

            # Nettoyer du HTML et prendre un échantillon
            sample = re.sub("<[^<]+?>", "", text)[:3000]

            if sample.strip():
                detected_lang = detect(sample)
                logger.info("Language detected from text: %s", detected_lang)
                return detected_lang

    except ImportError:
        logger.warning("langdetect library not available")
    except Exception:
        logger.info("Language detection failed.", exc_info=True)

    return None


def find_isbn_in_text(book: EpubBook) -> Optional[str]:
    """
    Recherche un ISBN dans le contenu textuel du livre.

    Fallback utilisé quand l'ISBN n'est pas dans les métadonnées.
    Scanne tous les documents XHTML à la recherche d'un ISBN valide.

    Args:
        book: Objet EpubBook

    Returns:
        ISBN canonique ou None si non trouvé
    """
    from ...config import ISBN_RE

    try:
        for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
            txt = item.get_content().decode("utf-8", errors="ignore")
            m = ISBN_RE.search(txt)

            if m:
                raw = m.group(0)
                # Valider que c'est bien un ISBN
                if is_isbn10(raw) or is_isbn13(raw):
                    isbn = canonical(raw)
                    logger.info("ISBN found in text: %s", isbn)
                    return isbn

    except Exception:
        logger.info("Text ISBN search failed.", exc_info=True)

    return None
