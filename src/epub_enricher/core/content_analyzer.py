# epub_enricher/src/epub_enricher/core/content_analyzer.py
"""
Analyse avancée du contenu EPUB pour extraire des métadonnées supplémentaires
"""

import logging
import re
from typing import Dict, Optional

from ebooklib import epub

from ..config import ISBN_RE

logger = logging.getLogger(__name__)


def extract_advanced_metadata(epub_path: str) -> Dict:
    """
    Extrait des métadonnées avancées depuis le contenu EPUB.

    Returns:
        Dict contenant les métadonnées extraites du contenu
    """
    data = {
        "content_isbn": None,
        "content_summary": None,
        "content_genre": None,
        "content_publisher": None,
        "content_publication_date": None,
        "content_edition_info": None,
        "content_analysis": {},
    }

    book = _safe_read_epub(epub_path)
    if not book:
        return data

    try:
        # 1. Recherche d'ISBN dans tout le contenu
        data["content_isbn"] = _extract_isbn_from_content(book)

        # 2. Extraction du résumé depuis les premières pages
        data["content_summary"] = _extract_summary_from_content(book)

        # 3. Détection du genre via analyse du contenu
        data["content_genre"] = _detect_genre_from_content(book)

        # 4. Recherche d'informations sur l'éditeur
        data["content_publisher"] = _extract_publisher_from_content(book)

        # 5. Extraction des dates de publication
        data["content_publication_date"] = _extract_publication_date_from_content(book)

        # 6. Informations d'édition détaillées
        data["content_edition_info"] = _extract_edition_info_from_content(book)

        # 7. Analyse générale du contenu
        data["content_analysis"] = _analyze_content_structure(book)

        logger.info(
            "Extracted advanced metadata for %s: %d fields",
            epub_path,
            len([k for k, v in data.items() if v]),
        )

    except Exception as e:
        logger.exception(f"Error extracting advanced metadata from {epub_path}: {e}")

    return data


def _safe_read_epub(epub_path: str) -> Optional[epub.EpubBook]:
    """Lit un fichier EPUB de manière sécurisée."""
    try:
        return epub.read_epub(epub_path)
    except Exception as e:
        logger.exception(f"Failed to read EPUB {epub_path}: {e}")
        return None


def _extract_isbn_from_content(book: epub.EpubBook) -> Optional[str]:
    """
    Recherche des ISBN dans tout le contenu du livre.
    """
    isbns_found = []

    try:
        # Recherche dans tous les documents
        for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
            try:
                content = item.get_content().decode("utf-8", errors="ignore")
                matches = ISBN_RE.findall(content)
                for match in matches:
                    # Nettoyer le match
                    clean_isbn = re.sub(r"[^\dX]", "", match)
                    if len(clean_isbn) in [10, 13]:
                        isbns_found.append(clean_isbn)
            except Exception:
                continue

        # Retourner le premier ISBN valide trouvé
        if isbns_found:
            logger.debug(f"Found ISBNs in content: {isbns_found}")
            return isbns_found[0]

    except Exception as e:
        logger.debug(f"Error extracting ISBN from content: {e}")

    return None


def _extract_summary_from_content(book: epub.EpubBook) -> Optional[str]:
    """
    Extrait un résumé depuis les premières pages du livre.
    """
    try:
        # Obtenir les documents dans l'ordre
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))

        # Limiter aux 3 premiers documents pour éviter de traiter tout le livre
        for doc in documents[:3]:
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                text = _clean_html_text(content)

                # Chercher des patterns de résumé
                summary = _find_summary_patterns(text)
                if summary:
                    logger.debug(f"Found summary in content: {summary[:100]}...")
                    return summary

            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error extracting summary from content: {e}")

    return None


def _detect_genre_from_content(book: epub.EpubBook) -> Optional[str]:
    """
    Détecte le genre du livre via analyse du contenu.
    """
    try:
        # Analyser les premiers chapitres
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))[:2]
        all_text = ""

        for doc in documents:
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                all_text += _clean_html_text(content) + " "
            except Exception:
                continue

        if not all_text.strip():
            return None

        # Analyse simple basée sur des mots-clés
        genre = _classify_genre_by_keywords(all_text[:5000])  # Limiter à 5000 caractères
        if genre:
            logger.debug(f"Detected genre from content: {genre}")
            return genre

    except Exception as e:
        logger.debug(f"Error detecting genre from content: {e}")

    return None


def _extract_publisher_from_content(book: epub.EpubBook) -> Optional[str]:
    """
    Recherche des informations sur l'éditeur dans le contenu.
    """
    try:
        # Chercher dans les pages de titre et les premiers documents
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))[:2]

        for doc in documents:
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                text = _clean_html_text(content)

                # Patterns pour trouver l'éditeur
                publisher = _find_publisher_patterns(text)
                if publisher:
                    logger.debug(f"Found publisher in content: {publisher}")
                    return publisher

            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error extracting publisher from content: {e}")

    return None


def _extract_publication_date_from_content(book: epub.EpubBook) -> Optional[str]:
    """
    Extrait les dates de publication depuis le contenu.
    """
    try:
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))[:2]

        for doc in documents:
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                text = _clean_html_text(content)

                # Chercher des patterns de date
                date = _find_date_patterns(text)
                if date:
                    logger.debug(f"Found publication date in content: {date}")
                    return date

            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error extracting publication date from content: {e}")

    return None


def _extract_edition_info_from_content(book: epub.EpubBook) -> Optional[Dict]:
    """
    Extrait des informations détaillées sur l'édition.
    """
    try:
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))[:2]
        edition_info = {}

        for doc in documents:
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                text = _clean_html_text(content)

                # Chercher des informations d'édition
                info = _find_edition_info_patterns(text)
                if info:
                    edition_info.update(info)

            except Exception:
                continue

        if edition_info:
            logger.debug(f"Found edition info in content: {edition_info}")
            return edition_info

    except Exception as e:
        logger.debug(f"Error extracting edition info from content: {e}")

    return None


def _analyze_content_structure(book: epub.EpubBook) -> Dict:
    """
    Analyse la structure générale du contenu.
    """
    analysis = {
        "total_documents": 0,
        "total_chapters": 0,
        "estimated_pages": 0,
        "language_confidence": 0.0,
        "content_type": "unknown",
    }

    try:
        documents = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
        analysis["total_documents"] = len(documents)

        # Estimer le nombre de pages (approximatif)
        total_chars = 0
        for doc in documents[:5]:  # Limiter aux 5 premiers
            try:
                content = doc.get_content().decode("utf-8", errors="ignore")
                text = _clean_html_text(content)
                total_chars += len(text)
            except Exception:
                continue

        # Estimation : ~2000 caractères par page
        analysis["estimated_pages"] = max(1, total_chars // 2000)

        # Détecter le type de contenu
        if analysis["total_documents"] > 10:
            analysis["content_type"] = "book"
        elif analysis["total_documents"] > 3:
            analysis["content_type"] = "novella"
        else:
            analysis["content_type"] = "short_story"

    except Exception as e:
        logger.debug(f"Error analyzing content structure: {e}")

    return analysis


# Fonctions utilitaires


def _clean_html_text(html_content: str) -> str:
    """Nettoie le HTML pour extraire le texte."""
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_summary_patterns(text: str) -> Optional[str]:
    """Trouve des patterns de résumé dans le texte."""
    # Patterns communs pour les résumés
    patterns = [
        r"(?:résumé|summary|abstract)[:\s]*(.{50,500})",
        r"(?:synopsis)[:\s]*(.{50,500})",
        r"(?:description)[:\s]*(.{50,500})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            summary = match.group(1).strip()
            if len(summary) > 50:  # Résumé valide
                return summary[:500]  # Limiter à 500 caractères

    return None


def _classify_genre_by_keywords(text: str) -> Optional[str]:
    """Classification simple du genre basée sur des mots-clés."""
    text_lower = text.lower()

    # Genres et leurs mots-clés
    genre_keywords = {
        "Fiction": ["roman", "histoire", "personnage", "intrigue"],
        "Science-Fiction": ["espace", "futur", "robot", "alien", "planète"],
        "Fantasy": ["magie", "sorcier", "dragon", "fantaisie", "enchanteur"],
        "Mystère": ["détective", "crime", "mystère", "enquête", "policier"],
        "Romance": ["amour", "romance", "cœur", "passion", "couple"],
        "Thriller": ["suspense", "tension", "danger", "poursuite", "menace"],
        "Biographie": ["vie", "biographie", "autobiographie", "mémoires"],
        "Histoire": ["historique", "guerre", "époque", "siècle", "batailles"],
    }

    # Compter les occurrences de mots-clés
    genre_scores = {}
    for genre, keywords in genre_keywords.items():
        score = sum(text_lower.count(keyword) for keyword in keywords)
        if score > 0:
            genre_scores[genre] = score

    # Retourner le genre avec le score le plus élevé
    if genre_scores:
        best_genre = max(genre_scores, key=genre_scores.get)
        if genre_scores[best_genre] >= 2:  # Seuil minimum
            return best_genre

    return None


def _find_publisher_patterns(text: str) -> Optional[str]:
    """Trouve des patterns d'éditeur dans le texte."""
    # Patterns pour les éditeurs
    patterns = [
        r"(?:éditeur|publisher|publié par)[:\s]*([A-Z][^,\.]{3,50})",
        r"(?:©|copyright)[^,]*([A-Z][^,\.]{3,50})",
        r"([A-Z][a-z]+ (?:Press|Éditions|Publishing|Books))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            publisher = match.group(1).strip()
            if len(publisher) > 3:
                return publisher

    return None


def _find_date_patterns(text: str) -> Optional[str]:
    """Trouve des patterns de date dans le texte."""
    # Patterns pour les dates
    patterns = [
        r"(?:publié|published|édition)[:\s]*(\d{4})",
        r"(?:©|copyright)[^,]*(\d{4})",
        r"(\d{4})[^,]*édition",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = match.group(1)
            if 1800 <= int(year) <= 2030:  # Année valide
                return year

    return None


def _find_edition_info_patterns(text: str) -> Dict:
    """Trouve des informations d'édition dans le texte."""
    info = {}

    # Numéro d'édition
    edition_match = re.search(r"(?:édition|edition)[:\s]*(\d+)", text, re.IGNORECASE)
    if edition_match:
        info["edition_number"] = edition_match.group(1)

    # Version
    version_match = re.search(r"(?:version|v)[:\s]*([\d\.]+)", text, re.IGNORECASE)
    if version_match:
        info["version"] = version_match.group(1)

    # Impression
    impression_match = re.search(r"(?:impression|printing)[:\s]*(\d+)", text, re.IGNORECASE)
    if impression_match:
        info["impression"] = impression_match.group(1)

    return info
