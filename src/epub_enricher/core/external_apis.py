# epub_enricher/src/epub_enricher/core/external_apis.py
"""
Intégration avec des APIs externes pour récupérer tags et résumé
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from epub_enricher.core.metadata_fetcher import download_cover, query_openlibrary_full
from epub_enricher.core.network_utils import http_get
from epub_enricher.core.text_utils import classify_genre_from_text, clean_html_text, clean_text

logger = logging.getLogger(__name__)

# Configuration des APIs
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
WIKIPEDIA_API = "https://fr.wikipedia.org/api/rest_v1/page/summary"
GOODREADS_API = "https://www.goodreads.com/search/index.xml"  # Nécessite une clé API

# ======================================================================
# --- Google Books Logic (Refactorisé) ---
# ======================================================================


def _parse_google_book(item: Dict) -> Dict[str, Any]:
    """Extrait les métadonnées d'un résultat Google Books."""
    info = item.get("volumeInfo", {})
    metadata: Dict[str, Any] = {}

    metadata["summary"] = clean_html_text(info.get("description", ""))

    raw_tags = info.get("categories") or info.get("subjects")
    if raw_tags:
        metadata["tags"] = [clean_text(t) for t in raw_tags if clean_text(t)]

    return metadata


def query_google_books(title: Optional[str] = None, isbn: Optional[str] = None) -> Dict[str, Any]:
    """Recherche Google Books par ISBN ou Titre."""
    if not (title or isbn):
        return {}

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


# ======================================================================
# --- Wikipedia Logic (Refactorisé) ---
# ======================================================================


def _parse_wiki_page(data: Dict) -> Optional[str]:
    """Extrait le résumé du résultat de l'API Wikipedia."""
    extract = data.get("extract_html")
    if extract:
        return clean_html_text(extract)
    return None


def query_wikipedia_summary(title: str) -> Optional[str]:
    """Récupère le résumé d'une page Wikipedia (fr)."""
    if not title:
        return None

    # L'API utilise le titre de la page encodé
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


# ======================================================================
# --- Agrégation et Mapping (Refactorisé) ---
# ======================================================================


def _map_tags_to_genre(tags: List[str]) -> Optional[str]:
    """Mappe les tags bruts d'une source vers un genre standard."""
    if not tags:
        return None

    for genre, keywords in GENRE_MAPPING.items():
        if any(tag.lower() in [k.lower() for k in keywords] for tag in tags):
            return genre

    return None


def _aggregate_genre(
    ol_tags: List[str], google_tags: List[str], summary_text: str
) -> Optional[str]:
    """Détermine le meilleur genre suggéré."""

    # 1. Priorité: Mapping des tags OpenLibrary
    genre_ol = _map_tags_to_genre(ol_tags)
    if genre_ol:
        logger.info("Genre set by OL Tag Mapping: %s", genre_ol)
        return genre_ol

    # 2. Priorité: Mapping des tags Google Books
    genre_google = _map_tags_to_genre(google_tags)
    if genre_google:
        logger.info("Genre set by Google Tag Mapping: %s", genre_google)
        return genre_google

    # 3. Fallback: Classification par mots-clés dans le résumé
    genre_text = classify_genre_from_text(summary_text)
    if genre_text:
        logger.info("Genre set by Text Classification: %s", genre_text)
        return genre_text

    return None


def fetch_genre_and_summary_from_sources(
    title: Optional[str] = None, authors: Optional[List[str]] = None, isbn: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fonction principale: interroge toutes les sources et agrège les résultats.
    """
    if not (title or isbn):
        logger.warning("Cannot fetch metadata without title or ISBN.")
        return {"genre": None, "summary": None, "cover_data": None}

    # 1. Interrogation des sources
    ol_data = query_openlibrary_full(title, authors, isbn)
    google_data = query_google_books(title, isbn)
    wiki_summary = query_wikipedia_summary(title)

    # 2. Agrégation des Résumés (meilleur effort)
    summary = ol_data.get("summary") or google_data.get("summary") or wiki_summary

    # 3. Agrégation du Genre
    genre = _aggregate_genre(
        ol_tags=ol_data.get("tags", []),
        google_tags=google_data.get("tags", []),
        summary_text=summary or "",
    )

    # 4. Couverture (via OpenLibrary uniquement)
    cover_data = None
    cover_id = ol_data.get("cover_id")
    if cover_id:
        cover_data = download_cover(cover_id)

    return {
        "genre": genre,
        "summary": summary,
        "tags": ol_data.get("tags", []) + google_data.get("tags", []),  # Fusion des tags
        "cover_data": cover_data,
        "ol_pub_date": ol_data.get("publication_date"),
        "ol_publisher": ol_data.get("publisher"),
    }


# Genres de mapping entre différentes sources
GENRE_MAPPING = {
    "Fiction": ["Fiction", "Literature", "Novel"],
    "Science-Fiction": ["Science Fiction", "Sci-Fi", "Fantasy", "Speculative Fiction"],
    "Fantasy": ["Fantasy", "Magic", "Fantasy Fiction"],
    "Mystery": ["Mystery", "Crime", "Detective", "Thriller"],
    "Romance": ["Romance", "Love", "Romantic Fiction"],
    "Thriller": ["Thriller", "Suspense", "Crime Fiction"],
    "Biography": ["Biography", "Autobiography", "Memoir"],
    "History": ["History", "Historical", "Non-fiction"],
    "Philosophy": ["Philosophy", "Philosophical"],
    "Religion": ["Religion", "Spirituality", "Religious"],
    "Science": ["Science", "Scientific", "Non-fiction"],
    "Art": ["Art", "Artistic", "Visual Arts"],
    "Poetry": ["Poetry", "Poems", "Verse"],
    "Drama": ["Drama", "Theatre", "Play"],
    "Children": ["Children's", "Kids", "Young Adult"],
}


def map_openlibrary_subject_to_genre(subject: str) -> Optional[str]:
    """Mappe un sujet OpenLibrary vers un genre standard."""
    subject_lower = subject.lower()

    for genre, keywords in GENRE_MAPPING.items():
        for keyword in keywords:
            if keyword.lower() in subject_lower:
                return genre

    return None
