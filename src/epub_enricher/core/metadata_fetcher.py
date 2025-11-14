# epub_enricher/src/epub_enricher/core/metadata_fetcher.py
"""
Logique pour interroger les APIs (OpenLibrary) et récupérer les métadonnées
"""

import logging
import os
from typing import Any, Dict, List, Optional

from epub_enricher.core.network_utils import http_download_bytes, http_get
from epub_enricher.core.text_utils import clean_text

from ..config import (
    COVER_CACHE_DIR,
    OPENLIB_SEARCH,
    ensure_directories,
)

logger = logging.getLogger(__name__)
OPENLIB_BASE = "https://openlibrary.org"


# ======================================================================
# --- OpenLibrary Logic ---
# ======================================================================


def _fetch_work_details(work_id: str) -> Optional[Dict]:
    """Récupère les détails de l'Œuvre (Work) OpenLibrary."""
    url = f"{OPENLIB_BASE}/works/{work_id}.json"
    try:
        r = http_get(url)
        return r.json()
    except Exception as e:
        logger.warning("Failed to fetch OL Work %s: %s", work_id, e)
        return None


def _fetch_edition_details(edition_id: str) -> Optional[Dict]:
    """Récupère les détails de l'Édition (Edition) OpenLibrary."""
    url = f"{OPENLIB_BASE}/books/{edition_id}.json"
    try:
        r = http_get(url)
        return r.json()
    except Exception as e:
        logger.warning("Failed to fetch OL Edition %s: %s", edition_id, e)
        return None


def extract_metadata_from_openlibrary(data: Dict, work_data: Optional[Dict]) -> Dict:
    """Extrait et nettoie les métadonnées depuis les résultats de l'API OpenLibrary."""
    metadata: Dict[str, Any] = {
        "summary": None,
        "tags": None,
        "publication_date": None,
        "publisher": None,
    }

    # 1. Résumé (Description) : Priorité à l'Œuvre, sinon l'Édition
    description_raw = None
    if work_data and work_data.get("description"):
        description_raw = work_data["description"]
    elif data.get("description"):
        description_raw = data["description"]

    if description_raw:
        # La description peut être une chaîne ou un dict {'type': '/type/text', 'value': '...'}
        summary = (
            description_raw.get("value")
            if isinstance(description_raw, dict)
            else str(description_raw)
        )
        metadata["summary"] = clean_text(summary)

    # 2. Sujets / Tags
    tags = data.get("subjects") or data.get("tags")
    if tags:
        # Nettoyage des tags pour retirer les tags vides ou trop longs
        metadata["tags"] = [clean_text(t) for t in tags if clean_text(t) and len(t) < 50]

    # 3. Date et Éditeur
    metadata["publication_date"] = data.get("publish_date")
    metadata["publisher"] = data.get("publishers", [None])[0]

    return metadata


def query_openlibrary_full(
    title: Optional[str] = None,
    authors: Optional[List[str]] = None,
    isbn: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tente une recherche OpenLibrary complète (ISBN -> Work -> Edition).
    Retourne les métadonnées enrichies.
    """
    result: Dict[str, Any] = {"summary": None, "tags": None, "cover_id": None}
    work_id: Optional[str] = None
    edition_id: Optional[str] = None

    try:
        # 1. Recherche initiale par ISBN ou titre/auteur

        # TOUJOURS utiliser l'API de recherche (OPENLIB_SEARCH)
        query_url = OPENLIB_SEARCH

        params = {}
        if isbn:
            # La recherche 'q' est la plus fiable pour un ISBN ou un texte
            params["q"] = isbn
        else:
            # Fallback sur titre/auteur si pas d'ISBN
            if title:
                params["title"] = title
            # Gérer le cas où 'authors' est None ou une liste vide
            if authors and len(authors) > 0 and authors[0]:
                params["author"] = authors[0]

        # Si on n'a ni ISBN, ni titre, ni auteur, on ne peut rien faire
        if not params:
            logger.info("OL: No ISBN, title, or author provided. Skipping search.")
            return result

        r = http_get(query_url, params=params)
        data = r.json()

        # 2. Trouver l'Edition/Work la plus pertinente
        docs = data.get("docs")
        if not docs:
            logger.info("OL: No result found for query: %s", params)
            return result

        # Prioriser le premier résultat, mais chercher les IDs
        doc = docs[0]
        work_id = doc.get("key", "").replace("/works/", "")

        # S'il n'y a pas de work_id, essayer de trouver une edition ID dans les ID existants
        if not work_id:
            edition_ids = doc.get("edition_key")
            edition_id = edition_ids[0] if edition_ids else None
            # On ne peut pas remonter au Work sans work_id, on s'arrête là pour la recherche avancée

        # 3. Récupérer les détails de l'Œuvre (Work) si possible
        work_data = _fetch_work_details(work_id) if work_id else None

        # 4. Récupérer les détails de l'Édition pour la date/éditeur (si pas d'ISBN)
        if edition_id:  # On fetch l'édition uniquement si on n'avait pas l'ISBN
            edition_data = _fetch_edition_details(edition_id)
        else:  # Si on a un ISBN, les détails de l'édition sont déjà dans 'doc' (première recherche)
            edition_data = doc

        # 5. Extraction finale
        final_data = work_data if work_data else edition_data  # Priorité à l'œuvre pour le résumé
        if final_data:
            result.update(extract_metadata_from_openlibrary(edition_data, work_data))

        # 6. ID de couverture (Open Library utilise un ID unique par travail ou édition)
        result["cover_id"] = doc.get("cover_i")

        result["related_docs"] = docs

        logger.info(
            "OL: Found metadata. Tags: %d, Summary: %s",
            len(result["tags"]) if result["tags"] else 0,
            "Yes" if result["summary"] else "No",
        )

    except Exception as e:
        logger.warning("Failed during full OL fetch: %s", e)

    return result


# ======================================================================
# --- Cover Cache Logic (Refactorisée pour être plus courte) ---
# ======================================================================


def _get_cover_from_cache(cover_id: int) -> Optional[bytes]:
    """Tente de charger une couverture depuis le cache."""
    cache_name = os.path.join(COVER_CACHE_DIR, f"{cover_id}.jpg")
    if os.path.exists(cache_name):
        with open(cache_name, "rb") as f:
            logger.debug("Loaded cover from cache %s", cache_name)
            return f.read()
    return None


def _download_and_cache_cover(cover_id: int, url: str) -> Optional[bytes]:
    """Télécharge la couverture et la met en cache."""
    cache_name = os.path.join(COVER_CACHE_DIR, f"{cover_id}.jpg")
    try:
        b = http_download_bytes(url)
        with open(cache_name, "wb") as f:
            f.write(b)
        logger.debug("Cached cover to %s", cache_name)
        return b
    except Exception as e:
        logger.warning("Failed to cache or download cover %s: %s", cache_name, e)
        # Supprimer le fichier s'il a été partiellement écrit
        if os.path.exists(cache_name):
            os.remove(cache_name)
        return None


def download_cover(cover_id: int) -> Optional[bytes]:
    """Télécharge la couverture depuis OpenLibrary, avec cache."""
    if not cover_id:
        return None

    ensure_directories()

    # 1. Vérifier le cache
    cached_data = _get_cover_from_cache(cover_id)
    if cached_data:
        return cached_data

    # 2. Télécharger et cacher
    url = f"{OPENLIB_BASE}/b/id/{cover_id}-L.jpg"
    return _download_and_cache_cover(cover_id, url)
