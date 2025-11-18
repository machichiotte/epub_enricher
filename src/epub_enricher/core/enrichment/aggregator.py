# epub_enricher/src/epub_enricher/core/enrichment/aggregator.py
"""
Agrégateur de métadonnées multi-sources.

Responsabilité unique: Orchestrer les appels aux différentes API externes
et agréger intelligemment leurs résultats.
"""

import logging
from typing import Any, Dict, List, Optional

from ..openlibrary_client import download_cover, query_openlibrary_full
from .genre_mapper import aggregate_genre
from .google_books import query_google_books
from .wikipedia import query_wikipedia_summary

logger = logging.getLogger(__name__)


def fetch_enriched_metadata(
    title: Optional[str] = None, authors: Optional[List[str]] = None, isbn: Optional[str] = None
) -> Dict[str, Any]:
    """
    Interroge toutes les sources externes et agrège les résultats.

    Cette fonction orchestre:
    - OpenLibrary (via openlibrary_client)
    - Google Books
    - Wikipedia

    Et agrège intelligemment leurs résultats selon un ordre de priorité.

    Args:
        title: Titre du livre
        authors: Liste des auteurs
        isbn: Code ISBN

    Returns:
        Dictionnaire avec les clés:
        - genre: Genre suggéré
        - summary: Résumé (meilleure source)
        - tags: Liste agrégée de tags
        - cover_data: Données de la couverture (bytes)
        - ol_pub_date: Date de publication (OpenLibrary)
        - ol_publisher: Éditeur (OpenLibrary)
    """
    if not (title or isbn):
        logger.warning("Cannot fetch metadata without title or ISBN.")
        return {
            "genre": None,
            "summary": None,
            "cover_data": None,
            "tags": [],
            "ol_pub_date": None,
            "ol_publisher": None,
        }

    # 1. Interrogation des sources en parallèle logique
    logger.debug(f"Fetching enriched metadata for: title={title}, isbn={isbn}")

    ol_data = query_openlibrary_full(title, authors, isbn)
    google_data = query_google_books(title, isbn)
    wiki_summary = query_wikipedia_summary(title) if title else None

    # 2. Agrégation des résumés (priorité: OL > Google > Wikipedia)
    summary = ol_data.get("summary") or google_data.get("summary") or wiki_summary

    # 3. Agrégation du genre (logique complexe dans genre_mapper)
    genre = aggregate_genre(
        ol_tags=ol_data.get("tags", []),
        google_tags=google_data.get("tags", []),
        summary_text=summary or "",
    )

    # 4. Agrégation des tags (fusion simple)
    all_tags = list(set((ol_data.get("tags") or []) + (google_data.get("tags") or [])))

    # 5. Couverture (via OpenLibrary uniquement - meilleure qualité)
    cover_data = None
    cover_id = ol_data.get("cover_id")
    if cover_id:
        cover_data = download_cover(cover_id)

    result = {
        "genre": genre,
        "summary": summary,
        "tags": all_tags,
        "cover_data": cover_data,
        "ol_pub_date": ol_data.get("publication_date"),
        "ol_publisher": ol_data.get("publisher"),
    }

    logger.info(
        "Enrichment complete: genre=%s, summary=%s, tags_count=%d",
        result["genre"],
        "Yes" if result["summary"] else "No",
        len(result["tags"]),
    )

    return result
