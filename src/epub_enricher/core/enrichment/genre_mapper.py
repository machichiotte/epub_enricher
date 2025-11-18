# epub_enricher/src/epub_enricher/core/enrichment/genre_mapper.py
"""
Mapping et classification de genres.

Responsabilité unique: Mapper les tags/catégories de différentes sources
vers un ensemble normalisé de genres standards.
"""

import logging
from typing import List, Optional

from ..text_utils import classify_genre_from_text

logger = logging.getLogger(__name__)

# Mapping de genres entre différentes sources vers des genres standards
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


def map_tags_to_genre(tags: List[str]) -> Optional[str]:
    """
    Mappe une liste de tags bruts vers un genre standard.

    Utilise le mapping GENRE_MAPPING pour identifier le premier genre
    correspondant dans la liste de tags.

    Args:
        tags: Liste de tags bruts (de Google Books, OpenLibrary, etc.)

    Returns:
        Genre standard ou None si aucun match
    """
    if not tags:
        return None

    for genre, keywords in GENRE_MAPPING.items():
        if any(tag.lower() in [k.lower() for k in keywords] for tag in tags):
            return genre

    return None


def map_openlibrary_subject_to_genre(subject: str) -> Optional[str]:
    """
    Mappe un sujet OpenLibrary vers un genre standard.

    Args:
        subject: Sujet OpenLibrary (chaîne de caractères)

    Returns:
        Genre standard ou None si aucun match
    """
    subject_lower = subject.lower()

    for genre, keywords in GENRE_MAPPING.items():
        for keyword in keywords:
            if keyword.lower() in subject_lower:
                return genre

    return None


def aggregate_genre(ol_tags: List[str], google_tags: List[str], summary_text: str) -> Optional[str]:
    """
    Détermine le meilleur genre en agrégeant plusieurs sources.

    Logique de priorité:
    1. Tags OpenLibrary (plus fiables pour les livres)
    2. Tags Google Books
    3. Classification par analyse du texte du résumé

    Args:
        ol_tags: Tags depuis OpenLibrary
        google_tags: Tags depuis Google Books
        summary_text: Texte du résumé pour analyse de fallback

    Returns:
        Genre suggéré ou None
    """
    # 1. Priorité: Mapping des tags OpenLibrary
    genre_ol = map_tags_to_genre(ol_tags)
    if genre_ol:
        logger.info("Genre set by OL Tag Mapping: %s", genre_ol)
        return genre_ol

    # 2. Priorité: Mapping des tags Google Books
    genre_google = map_tags_to_genre(google_tags)
    if genre_google:
        logger.info("Genre set by Google Tag Mapping: %s", genre_google)
        return genre_google

    # 3. Fallback: Classification par mots-clés dans le résumé
    genre_text = classify_genre_from_text(summary_text)
    if genre_text:
        logger.info("Genre set by Text Classification: %s", genre_text)
        return genre_text

    return None
