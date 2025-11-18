# epub_enricher/src/epub_enricher/core/enrichment/wikipedia.py
"""
Client Wikipedia API.

Responsabilité unique: Interroger l'API Wikipedia (fr) pour obtenir
des résumés d'articles liés aux livres.
"""

import logging
from typing import Optional
from urllib.parse import quote

from ..network_utils import http_get
from ..text_utils import clean_html_text

logger = logging.getLogger(__name__)

# Configuration API
WIKIPEDIA_API = "https://fr.wikipedia.org/api/rest_v1/page/summary"


def _parse_wiki_page(data: dict) -> Optional[str]:
    """
    Extrait le résumé du résultat de l'API Wikipedia.

    Args:
        data: Résultat JSON de l'API Wikipedia

    Returns:
        Résumé nettoyé ou None
    """
    extract = data.get("extract_html")
    if extract:
        return clean_html_text(extract)
    return None


def query_wikipedia_summary(title: str) -> Optional[str]:
    """
    Récupère le résumé d'une page Wikipedia (version française).

    Args:
        title: Titre de la page Wikipedia (généralement le titre du livre)

    Returns:
        Résumé de la page ou None si non trouvé

    Note:
        Utilise l'API REST Wikipedia qui ne nécessite pas de clé.
        Le titre doit correspondre exactement au titre de la page Wikipedia.
    """
    if not title:
        return None

    # L'API utilise le titre de la page encodé dans l'URL
    encoded_title = quote(title, safe="")
    url = f"{WIKIPEDIA_API}/{encoded_title}"

    try:
        r = http_get(url)
        data = r.json()
        logger.info("Wikipedia: Found summary for %s.", title)
        return _parse_wiki_page(data)

    except Exception as e:
        logger.info("Failed to get Wikipedia summary for '%s': %s", title, e)
        return None
