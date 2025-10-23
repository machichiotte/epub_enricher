"""
Intégration avec des APIs externes pour récupérer genre et résumé
"""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from ..config import API_TIMEOUT

logger = logging.getLogger(__name__)

# Configuration des APIs
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
WIKIPEDIA_API = "https://fr.wikipedia.org/api/rest_v1/page/summary"
GOODREADS_API = "https://www.goodreads.com/search/index.xml"  # Nécessite une clé API

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


def fetch_genre_and_summary_from_sources(
    title: str, authors: List[str] = None, isbn: str = None
) -> Dict[str, Optional[str]]:
    """
    Récupère le genre et le résumé depuis plusieurs sources.

    Args:
        title: Titre du livre
        authors: Liste des auteurs
        isbn: ISBN du livre

    Returns:
        Dict avec 'genre' et 'summary' depuis différentes sources
    """
    results = {
        "genre": None,
        "summary": None,
        "sources": {
            "google_books": {"genre": None, "summary": None},
            "wikipedia": {"genre": None, "summary": None},
            "openlibrary": {"genre": None, "summary": None},
        },
    }

    try:
        # 1. Google Books API
        google_data = query_google_books(title, authors, isbn)
        if google_data:
            results["sources"]["google_books"]["genre"] = google_data.get("genre")
            results["sources"]["google_books"]["summary"] = google_data.get("summary")

            # Utiliser Google Books comme source principale si disponible
            if not results["genre"] and google_data.get("genre"):
                results["genre"] = google_data["genre"]
            if not results["summary"] and google_data.get("summary"):
                results["summary"] = google_data["summary"]

        # 2. Wikipedia API
        wiki_data = query_wikipedia_summary(title, authors)
        if wiki_data:
            results["sources"]["wikipedia"]["genre"] = wiki_data.get("genre")
            results["sources"]["wikipedia"]["summary"] = wiki_data.get("summary")

            # Utiliser Wikipedia si pas de données Google Books
            if not results["genre"] and wiki_data.get("genre"):
                results["genre"] = wiki_data["genre"]
            if not results["summary"] and wiki_data.get("summary"):
                results["summary"] = wiki_data["summary"]

        # 3. OpenLibrary (déjà implémenté, mais on peut l'étendre)
        ol_data = query_openlibrary_genre_summary(title, authors, isbn)
        if ol_data:
            results["sources"]["openlibrary"]["genre"] = ol_data.get("genre")
            results["sources"]["openlibrary"]["summary"] = ol_data.get("summary")

            # Utiliser OpenLibrary si pas d'autres sources
            if not results["genre"] and ol_data.get("genre"):
                results["genre"] = ol_data["genre"]
            if not results["summary"] and ol_data.get("summary"):
                results["summary"] = ol_data["summary"]

        logger.info(
            "Fetched genre and summary for '%s': genre=%s, summary=%s",
            title,
            results.get("genre"),
            "Yes" if results.get("summary") else "No",
        )

    except Exception as e:
        logger.exception(f"Error fetching genre and summary for '{title}': {e}")

    return results


def query_google_books(title: str, authors: List[str] = None, isbn: str = None) -> Optional[Dict]:
    """
    Interroge l'API Google Books pour récupérer genre et résumé.
    """
    try:
        # Construire la requête
        query_parts = [title]
        if authors:
            query_parts.append(" ".join(authors[:2]))  # Limiter à 2 auteurs
        if isbn:
            query_parts.append(f"isbn:{isbn}")

        query = " ".join(query_parts)
        params = {"q": query, "maxResults": 1, "printType": "books"}

        response = requests.get(GOOGLE_BOOKS_API, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        if not data.get("items"):
            logger.debug(f"No Google Books results for '{title}'")
            return None

        book = data["items"][0]["volumeInfo"]

        # Extraire le genre depuis les catégories
        genre = extract_genre_from_google_books(book)

        # Extraire le résumé
        summary = book.get("description", "")
        if summary:
            # Nettoyer le résumé (supprimer les balises HTML)
            summary = clean_html_text(summary)
            # Limiter la longueur
            if len(summary) > 1000:
                summary = summary[:1000] + "..."

        result = {
            "genre": genre,
            "summary": summary if summary else None,
            "title": book.get("title", ""),
            "authors": book.get("authors", []),
            "published_date": book.get("publishedDate", ""),
        }

        logger.debug(f"Google Books result for '{title}': {result}")
        return result

    except Exception as e:
        logger.warning(f"Google Books API error for '{title}': {e}")
        return None


def query_wikipedia_summary(title: str, authors: List[str] = None) -> Optional[Dict]:
    """
    Interroge l'API Wikipedia pour récupérer un résumé.
    """
    try:
        # Construire le titre de recherche
        search_title = title
        if authors:
            # Ajouter le nom de l'auteur principal
            search_title = f"{title} ({authors[0]})"

        # Encoder l'URL
        encoded_title = quote(search_title)
        url = f"{WIKIPEDIA_API}/{encoded_title}"

        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 404:
            logger.debug(f"Wikipedia page not found for '{title}'")
            return None

        response.raise_for_status()
        data = response.json()

        # Extraire le résumé
        summary = data.get("extract", "")
        if summary:
            # Nettoyer et limiter
            summary = clean_text(summary)
            if len(summary) > 1000:
                summary = summary[:1000] + "..."

        # Essayer de détecter le genre depuis le résumé
        genre = classify_genre_from_text(summary) if summary else None

        result = {
            "genre": genre,
            "summary": summary if summary else None,
            "title": data.get("title", ""),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        }

        logger.debug(
            f"Wikipedia result for '{title}': genre={genre}, summary={'Yes' if summary else 'No'}"
        )
        return result

    except Exception as e:
        logger.warning(f"Wikipedia API error for '{title}': {e}")
        return None


def query_openlibrary_genre_summary(
    title: str, authors: List[str] = None, isbn: str = None
) -> Optional[Dict]:
    """
    Étend OpenLibrary pour récupérer genre et résumé depuis work_details.
    """
    try:
        from .metadata_fetcher import query_openlibrary_full

        # Utiliser la fonction existante
        results = query_openlibrary_full(title, authors, isbn)

        genre = None
        summary = None

        # Chercher dans les résultats
        if results.get("by_isbn"):
            data = results["by_isbn"]
            genre = extract_genre_from_openlibrary(data)
            summary = extract_summary_from_openlibrary(data)

        # Chercher dans les éditions liées
        for doc in results.get("related_docs", []):
            if not genre:
                genre = extract_genre_from_openlibrary(doc)
            if not summary:
                summary = extract_summary_from_openlibrary(doc)

            # Chercher dans work_details
            work_details = doc.get("work_details", {})
            if work_details:
                if not genre:
                    genre = extract_genre_from_openlibrary(work_details)
                if not summary:
                    summary = extract_summary_from_openlibrary(work_details)

        if genre or summary:
            result = {
                "genre": genre,
                "summary": summary,
            }
            logger.debug(f"OpenLibrary genre/summary for '{title}': {result}")
            return result

    except Exception as e:
        logger.warning(f"OpenLibrary genre/summary error for '{title}': {e}")

    return None


def extract_genre_from_google_books(book_data: Dict) -> Optional[str]:
    """Extrait le genre depuis les données Google Books."""
    try:
        categories = book_data.get("categories", [])
        if not categories:
            return None

        # Prendre la première catégorie et la mapper
        raw_category = categories[0]
        genre = map_google_books_category_to_genre(raw_category)

        if genre:
            logger.debug(f"Mapped Google Books category '{raw_category}' to genre '{genre}'")
            return genre

    except Exception as e:
        logger.debug(f"Error extracting genre from Google Books: {e}")

    return None


def extract_genre_from_openlibrary(data: Dict) -> Optional[str]:
    """Extrait le genre depuis les données OpenLibrary."""
    try:
        # Chercher dans les sujets
        subjects = data.get("subjects", [])
        if subjects:
            # Prendre le premier sujet et le mapper
            raw_subject = (
                subjects[0] if isinstance(subjects[0], str) else subjects[0].get("name", "")
            )
            genre = map_openlibrary_subject_to_genre(raw_subject)
            if genre:
                return genre

        # Chercher dans les classifications
        classifications = data.get("subject_places", []) + data.get("subject_people", [])
        if classifications:
            # Essayer de classifier depuis le texte
            text = " ".join(classifications)
            genre = classify_genre_from_text(text)
            if genre:
                return genre

    except Exception as e:
        logger.debug(f"Error extracting genre from OpenLibrary: {e}")

    return None


def extract_summary_from_openlibrary(data: Dict) -> Optional[str]:
    """Extrait le résumé depuis les données OpenLibrary."""
    try:
        description = data.get("description", "")
        if not description:
            return None

        # Gérer les différents formats de description
        if isinstance(description, dict):
            description = description.get("value", "")

        if description:
            # Nettoyer le texte
            summary = clean_html_text(description)
            # Limiter la longueur
            if len(summary) > 1000:
                summary = summary[:1000] + "..."
            return summary

    except Exception as e:
        logger.debug(f"Error extracting summary from OpenLibrary: {e}")

    return None


def map_google_books_category_to_genre(category: str) -> Optional[str]:
    """Mappe une catégorie Google Books vers un genre standard."""
    category_lower = category.lower()

    for genre, keywords in GENRE_MAPPING.items():
        for keyword in keywords:
            if keyword.lower() in category_lower:
                return genre

    return None


def map_openlibrary_subject_to_genre(subject: str) -> Optional[str]:
    """Mappe un sujet OpenLibrary vers un genre standard."""
    subject_lower = subject.lower()

    for genre, keywords in GENRE_MAPPING.items():
        for keyword in keywords:
            if keyword.lower() in subject_lower:
                return genre

    return None


def classify_genre_from_text(text: str) -> Optional[str]:
    """Classification automatique du genre basée sur le texte."""
    if not text:
        return None

    text_lower = text.lower()

    # Mots-clés pour la classification
    genre_keywords = {
        "Fiction": ["roman", "histoire", "personnage", "intrigue", "fiction"],
        "Science-Fiction": ["espace", "futur", "robot", "alien", "planète", "science fiction"],
        "Fantasy": ["magie", "sorcier", "dragon", "fantaisie", "enchanteur", "fantasy"],
        "Mystery": ["détective", "crime", "mystère", "enquête", "policier", "mystery"],
        "Romance": ["amour", "romance", "cœur", "passion", "couple", "love"],
        "Thriller": ["suspense", "tension", "danger", "poursuite", "menace", "thriller"],
        "Biography": ["vie", "biographie", "autobiographie", "mémoires", "biography"],
        "History": ["historique", "guerre", "époque", "siècle", "batailles", "history"],
        "Philosophy": ["philosophie", "philosophique", "philosophy"],
        "Science": ["science", "scientifique", "science"],
        "Art": ["art", "artistique", "art"],
        "Poetry": ["poésie", "poème", "poetry"],
    }

    # Compter les occurrences
    genre_scores = {}
    for genre, keywords in genre_keywords.items():
        score = sum(text_lower.count(keyword) for keyword in keywords)
        if score > 0:
            genre_scores[genre] = score

    # Retourner le genre avec le score le plus élevé
    if genre_scores:
        best_genre = max(genre_scores, key=genre_scores.get)
        if genre_scores[best_genre] >= 1:  # Seuil minimum
            return best_genre

    return None


def clean_html_text(html_content: str) -> str:
    """Nettoie le HTML pour extraire le texte."""
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Nettoie le texte général."""
    # Supprimer les caractères spéciaux
    text = re.sub(r"[^\w\s.,!?;:-]", " ", text)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()
