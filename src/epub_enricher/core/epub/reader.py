# epub_enricher/src/epub_enricher/core/epub/reader.py
"""
Module de lecture EPUB.

Responsabilité unique: Extraire les métadonnées depuis les fichiers EPUB.
"""

import logging
from typing import Any, Dict, List, Optional

from ebooklib import epub
from ebooklib.epub import EpubBook

from .cover_finder import find_cover_data
from .metadata_extractors import detect_language_from_text, find_isbn_in_text

logger = logging.getLogger(__name__)


def safe_read_epub(epub_path: str) -> Optional[EpubBook]:
    """
    Lit un fichier EPUB de manière sécurisée.
    
    Args:
        epub_path: Chemin vers le fichier EPUB
        
    Returns:
        Objet EpubBook si succès, None sinon
    """
    try:
        return epub.read_epub(epub_path)
    except Exception as e:
        logger.exception("ebooklib failed to read %s: %s", epub_path, e)
        return None


# --- Extracteurs de métadonnées de base ---


def _get_metadata_field(book: EpubBook, namespace: str, name: str) -> Optional[Any]:
    """
    Helper générique pour extraire un champ de métadonnées.
    
    Args:
        book: Objet EpubBook
        namespace: Namespace de métadonnées (ex: 'DC')
        name: Nom du champ (ex: 'title')
        
    Returns:
        Valeur du champ ou None
    """
    try:
        meta = book.get_metadata(namespace, name)
        if meta:
            return meta[0][0]
    except Exception:
        pass  # Le logging sera fait par l'appelant si nécessaire
    return None


def _get_title(book: EpubBook) -> Optional[str]:
    """Extrait le titre du livre."""
    return _get_metadata_field(book, "DC", "title")


def _get_publisher(book: EpubBook) -> Optional[str]:
    """Extrait l'éditeur du livre."""
    return _get_metadata_field(book, "DC", "publisher")


def _get_date(book: EpubBook) -> Optional[str]:
    """Extrait la date de publication."""
    return _get_metadata_field(book, "DC", "date")


def _get_summary(book: EpubBook) -> Optional[str]:
    """Extrait le résumé/description."""
    return _get_metadata_field(book, "DC", "description")


def _get_language(book: EpubBook) -> Optional[str]:
    """Extrait la langue du livre."""
    return _get_metadata_field(book, "DC", "language")


def _get_authors(book: EpubBook) -> Optional[List[str]]:
    """
    Extrait la liste des auteurs.
    
    Returns:
        Liste des auteurs ou None si aucun trouvé
    """
    try:
        auths_meta = book.get_metadata("DC", "creator")
        authors = []
        for a in auths_meta:
            authors.append(a[0] if isinstance(a, tuple) else str(a))
        return authors if authors else None
    except Exception:
        return None


def _get_tags(book: EpubBook) -> Optional[List[str]]:
    """
    Extrait les sujets/tags.
    
    Returns:
        Liste des tags ou None si aucun trouvé
    """
    try:
        subj_meta = book.get_metadata("DC", "subject")
        return [s[0] for s in subj_meta if s[0]] or None
    except Exception:
        return None


def _get_identifier(book: EpubBook) -> Optional[str]:
    """
    Extrait l'ISBN canonique depuis les identifiants.
    
    Returns:
        ISBN canonique ou None
    """
    from isbnlib import canonical, is_isbn10, is_isbn13
    
    from ...config import ISBN_RE
    
    try:
        ids_meta = book.get_metadata("DC", "identifier")
        for ident in ids_meta:
            candidate = ident[0]
            if isinstance(candidate, str) and ISBN_RE.search(candidate):
                m = ISBN_RE.search(candidate).group(0)
                if is_isbn10(m) or is_isbn13(m):
                    return canonical(m)
    except Exception:
        return None
    return None


# --- Fonction principale d'extraction ---


def extract_metadata(epub_path: str) -> Dict:
    """
    Extrait toutes les métadonnées d'un fichier EPUB.
    
    Cette fonction orchestre l'extraction de toutes les métadonnées
    disponibles et utilise des stratégies de fallback pour les
    données manquantes (langue, ISBN).
    
    Args:
        epub_path: Chemin vers le fichier EPUB
        
    Returns:
        Dictionnaire contenant toutes les métadonnées extraites.
        Les clés possibles sont: title, authors, language, identifier,
        publisher, date, tags, summary, cover_data
    """
    # Initialiser le dictionnaire de résultats
    data = {
        k: None
        for k in [
            "title",
            "authors",
            "language",
            "identifier",
            "publisher",
            "date",
            "tags",
            "summary",
            "cover_data",
        ]
    }
    
    # Lire le fichier EPUB
    book = safe_read_epub(epub_path)
    if not book:
        logger.warning("Could not read EPUB file: %s", epub_path)
        return data

    # Extraction des métadonnées de base
    data["title"] = _get_title(book)
    data["authors"] = _get_authors(book)
    data["language"] = _get_language(book)
    data["identifier"] = _get_identifier(book)
    data["publisher"] = _get_publisher(book)
    data["date"] = _get_date(book)
    data["summary"] = _get_summary(book)
    data["tags"] = _get_tags(book)
    
    # Extraction de la couverture
    data["cover_data"] = find_cover_data(book, epub_path)

    # Logique de fallback pour les métadonnées manquantes
    if not data["language"]:
        data["language"] = detect_language_from_text(book)
        
    if not data["identifier"]:
        data["identifier"] = find_isbn_in_text(book)

    logger.info("Extracted metadata for %s", epub_path)
    return data
