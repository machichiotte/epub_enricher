# epub_enricher/src/epub_enricher/core/enrichment/google_books.py
"""
Client Google Books API.

Responsabilité unique: Interroger l'API Google Books pour obtenir
des métadonnées complémentaires (résumé, tags/catégories).
"""

import logging
from typing import Any, Dict, Optional

from ..network_utils import http_get
from ..text_utils import clean_html_text, clean_text

logger = logging.getLogger(__name__)

# Configuration API
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


def _parse_google_book(item: Dict) -> Dict[str, Any]:
    """
    Extrait les métadonnées d'un résultat Google Books.
    
    Args:
        item: Résultat JSON de l'API Google Books
        
    Returns:
        Dictionnaire avec les clés 'summary' et 'tags'
    """
    info = item.get("volumeInfo", {})
    metadata: Dict[str, Any] = {}

    # Extraction du résumé (description)
    metadata["summary"] = clean_html_text(info.get("description", ""))

    # Extraction des catégories/sujets
    raw_tags = info.get("categories") or info.get("subjects")
    if raw_tags:
        metadata["tags"] = [clean_text(t) for t in raw_tags if clean_text(t)]

    return metadata


def query_google_books(title: Optional[str] = None, isbn: Optional[str] = None) -> Dict[str, Any]:
    """
    Recherche Google Books par ISBN ou titre.
    
    Args:
        title: Titre du livre (optionnel)
        isbn: Code ISBN (optionnel)
        
    Returns:
        Dictionnaire avec les métadonnées trouvées (summary, tags) ou {}
        
    Note:
        L'ISBN est prioritaire sur le titre si les deux sont fournis
    """
    if not (title or isbn):
        return {}

    # Construction de la requête (priorité ISBN)
    query = f"isbn:{isbn}" if isbn else f"intitle:{title}"
    params = {"q": query, "maxResults": 1, "langRestrict": "fr|en"}

    try:
        r = http_get(GOOGLE_BOOKS_API, params=params)
        data = r.json()
        items = data.get("items")

        if items:
            logger.info("Google Books: Found result.")
            return _parse_google_book(items[0])

    except Exception as e:
        logger.warning("Failed during Google Books query: %s", e)

    return {}
