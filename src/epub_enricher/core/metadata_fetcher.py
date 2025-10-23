# epub_enricher/src/epub_enricher/core/metadata_fetcher.py
"""
Logique pour interroger les APIs (OpenLibrary) et récupérer les métadonnées
"""

import hashlib
import json
import logging
import os
import random
import time
from functools import wraps
from typing import Callable, Dict, List, Optional

import requests

from ..config import (
    API_TIMEOUT,
    COVER_CACHE_DIR,
    INITIAL_BACKOFF,
    JITTER,
    MAX_BACKOFF,
    MAX_RETRIES,
    OPENLIB_BOOK,
    OPENLIB_SEARCH,
    ensure_directories,
)

logger = logging.getLogger(__name__)
OPENLIB_BASE = "https://openlibrary.org"


# ======================================================================
# --- Infrastructure réseau : retry + HTTP ---
# ======================================================================


def retry_backoff(
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
    max_backoff: float = MAX_BACKOFF,
    jitter: float = JITTER,
    allowed_exceptions: tuple = (requests.RequestException,),
):
    """Decorator for retrying functions with exponential backoff + jitter."""

    def deco(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            backoff = initial_backoff
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug("Attempt %d for %s", attempt, func.__name__)
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    if attempt == max_retries:
                        logger.exception("Max retries reached for %s", func.__name__)
                        raise
                    sleep_time = backoff * (1 + random.uniform(-jitter, jitter))
                    sleep_time = max(0.0, min(max_backoff, sleep_time))
                    logger.warning(
                        "Error on attempt %d for %s: %s -- backing off %.2fs",
                        attempt,
                        func.__name__,
                        e,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    backoff = min(max_backoff, backoff * 2)
                except Exception:
                    logger.exception("Non-retryable exception in %s", func.__name__)
                    raise

        return wrapper

    return deco


@retry_backoff()
def http_get(
    url: str,
    params: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = API_TIMEOUT,
) -> requests.Response:
    """Effectue une requête HTTP GET avec retry automatique."""
    logger.debug("HTTP GET %s params=%s", url, params)
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


@retry_backoff()
def http_download_bytes(url: str, timeout: int = API_TIMEOUT) -> bytes:
    """Télécharge des données binaires avec retry automatique."""
    logger.debug("Downloading bytes from %s", url)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


# ======================================================================
# --- Fonctions principales de récupération de données ---
# ======================================================================


def fetch_openlibrary_work_details(work_key: str) -> dict:
    """Récupère les détails complets d'une œuvre OpenLibrary (/works/xxx.json)."""
    url = f"{OPENLIB_BASE}{work_key}.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            logger.info(f"Fetched work details for {work_key}")
            return data
        else:
            logger.warning(f"Work {work_key} not found: {r.status_code}")
    except Exception as e:
        logger.error(f"Error fetching work {work_key}: {e}")
    return {}


def fetch_openlibrary_edition_details(edition_key: str) -> dict:
    """Récupère les détails complets d'une édition OpenLibrary (/books/xxx.json)."""

    # S'assurer que la clé n'a pas de préfixe (ex: /books/OL123M -> OL123M)
    if edition_key.startswith("/books/"):
        edition_key = edition_key.replace("/books/", "")

    url = f"{OPENLIB_BASE}/books/{edition_key}.json"
    try:
        # On utilise requests.get directement, comme fetch_openlibrary_work_details
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            logger.info(f"Fetched edition details for {edition_key}")
            return data
        else:
            logger.warning(f"Edition {edition_key} not found: {r.status_code}")
    except Exception as e:
        logger.error(f"Error fetching edition {edition_key}: {e}")
    return {}


def query_openlibrary_full(
    title: Optional[str] = None, authors: Optional[List[str]] = None, isbn: Optional[str] = None
) -> Dict[str, List[Dict]]:
    """
    Combine les recherches par ISBN et par (titre + auteur) pour regrouper toutes les éditions
    d'une même œuvre. Retourne un dict avec 'by_isbn' et 'related_docs'.
    """
    results = {"by_isbn": None, "related_docs": []}

    # 1️⃣ Recherche directe par ISBN
    if isbn:
        data = query_openlibrary_by_isbn(isbn)
        if data:
            results["by_isbn"] = data

    # 2️⃣ Recherche complémentaire par titre/auteur
    if title:
        auth = authors[0] if authors else None
        docs = query_openlibrary_search_all(title, auth)
        if docs:
            results["related_docs"] = docs

    # 3️⃣ Récupération des détails des œuvres (works)
    for doc in results.get("related_docs", []):
        work_key = doc.get("key")
        if work_key:
            work_data = fetch_openlibrary_work_details(work_key)
            if work_data:
                doc["work_details"] = work_data
        edition_key = doc.get("cover_edition_key")
        if edition_key:
            # La fonction fetch_openlibrary_edition_details gère déjà
            # le préfixe /books/ si besoin.
            edition_data = fetch_openlibrary_edition_details(edition_key)
            if edition_data:
                doc["edition_details"] = edition_data

    # --- LOGS DÉTAILLÉS POUR DIAGNOSTIC ---
    if results.get("by_isbn"):
        data = results["by_isbn"]
        publishers = data.get("publishers", [])
        if publishers and isinstance(publishers[0], dict):
            publisher_name = publishers[0].get("name", "")
        elif publishers and isinstance(publishers[0], str):
            publisher_name = publishers[0]
        else:
            publisher_name = ""

        isbn_list = data.get("isbn_13", []) + data.get("isbn_10", [])
        langs = [
            lang_entry.get("key", "").split("/")[-1]
            for lang_entry in data.get("languages", [])
            if isinstance(lang_entry, dict)
        ]

        logger.info("=== OpenLibrary ISBN metadata ===")
        logger.info(
            "Title: %s | Authors: %s | Publisher: %s | ISBN: %s | Lang: %s",
            data.get("title"),
            ", ".join([a.get("key", "").split("/")[-1] for a in data.get("authors", [])]),
            publisher_name,
            ", ".join(isbn_list),
            ", ".join(langs),
        )

    docs = results.get("related_docs", [])
    if docs:
        logger.info("=== OpenLibrary related editions ===")
        for i, doc in enumerate(docs, start=1):
            title = doc.get("title", "")
            authors = ", ".join(doc.get("author_name", [])) if doc.get("author_name") else ""
            has_work = "✅" if "work_details" in doc else "❌"
            has_edition = "✅" if "edition_details" in doc else "❌"  # Pour vérifier

            # Valeurs par défaut (celles de la recherche, souvent vides)
            lang = ", ".join(doc.get("language", [])) if doc.get("language") else ""
            isbns = ", ".join(doc.get("isbn", [])[:3]) if doc.get("isbn") else ""
            publisher = ", ".join(doc.get("publisher", [])) if doc.get("publisher") else ""
            year = str(doc.get("first_publish_year", ""))

            # Si on a les détails de l'édition, on les utilise car ils sont meilleurs
            if "edition_details" in doc:
                details = doc["edition_details"]

                # Affiche toutes les clés principales reçues pour ce "edition"
                logger.info(f"    -> Clés reçues pour Edition [{i}]: {list(details.keys())}")
                logger.info(f"    -> Valeurs reçues pour Edition [{i}]: {details}")

                # Langue
                langs_obj = details.get("languages", [])
                if langs_obj:
                    lang = ", ".join(
                        [
                            lang_entry.get("key", "").split("/")[-1]
                            for lang_entry in langs_obj
                            if isinstance(lang_entry, dict)
                        ]
                    )

                # ISBNs
                isbn_list = details.get("isbn_13", []) + details.get("isbn_10", [])
                if isbn_list:
                    isbns = ", ".join(isbn_list[:3])  # Limite à 3

                # Publisher
                pubs_obj = details.get("publishers", [])
                if pubs_obj:
                    # Le format varie : parfois liste de strings, parfois liste de dicts
                    if pubs_obj and isinstance(pubs_obj[0], dict):
                        publisher = ", ".join([p.get("name") for p in pubs_obj if p.get("name")])
                    else:
                        publisher = ", ".join(pubs_obj)  # Liste de strings

                # Année (plus précise depuis l'édition)
                if details.get("publish_date"):
                    year = details.get("publish_date")  # ex: "2018" ou "Juin 2018"

            logger.info(
                f"[{i}] {title} | Lang: {lang} | ISBN: {isbns} | Publisher: {publisher} | "
                f"Year: {year} | Authors: {authors} | Work: {has_work} | Edition: {has_edition}"
            )

            # Ajout pour logger la description (si elle existe)
            if "work_details" in doc:
                details = doc["work_details"]

                # Affiche toutes les clés principales reçues pour ce "work"
                logger.info(f"    -> Clés reçues pour Work [{i}]: {list(details.keys())}")
                logger.info(f"    -> Valeurs reçues pour Work [{i}]: {details}")

                description = details.get("description", "Pas de description.")

                # Parfois la description est un objet {"type": "...", "value": "..."}
                if isinstance(description, dict):
                    description = description.get("value", "Pas de description (format objet).")

                # Limite l'affichage aux 200 premiers caractères pour éviter de noyer les logs
                logger.info(f"    -> Description [{i}]: {description[:200]}...")

    logger.info("===================================")
    return results


def query_openlibrary_search_all(title: str, author: Optional[str] = None) -> Optional[List[Dict]]:
    """Retourne TOUTES les éditions correspondantes à un titre/auteur."""
    try:
        q = title
        if author:
            q += f" {author}"
        params = {"q": q, "title": title, "limit": 20}
        r = http_get(OPENLIB_SEARCH, params=params)
        js = r.json()
        docs = js.get("docs", [])
        logger.info("OpenLibrary search returned %d docs for query %s", len(docs), q)

        # 🧠 LOG COMPLET — pour visualiser la structure brute
        logger.info("=== RAW DOCS FROM SEARCH ===")
        logger.info(json.dumps(docs, indent=2, ensure_ascii=False))
        logger.info("===================================")

        return docs
    except Exception as e:
        logger.warning("query_openlibrary_search_all failed for %s / %s: %s", title, author, e)
    return None


def query_openlibrary_by_isbn(isbn: str) -> Optional[Dict]:
    """Interroge OpenLibrary avec un ISBN pour récupérer les métadonnées."""
    try:
        params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
        r = http_get(OPENLIB_BOOK, params=params)
        js = r.json()
        key = f"ISBN:{isbn}"
        if key in js:
            logger.info("OpenLibrary returned data for ISBN %s", isbn)
            return js[key]
        logger.info("OpenLibrary no data for ISBN %s", isbn)
    except Exception as e:
        logger.warning("query_openlibrary_by_isbn failed for %s: %s", isbn, e)
    return None


def download_cover(url: str) -> Optional[bytes]:
    """Télécharge et cache une image de couverture."""
    try:
        ensure_directories()
        name = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".jpg"
        cache_name = os.path.join(COVER_CACHE_DIR, name)
        if os.path.exists(cache_name):
            with open(cache_name, "rb") as f:
                logger.debug("Loaded cover from cache %s", cache_name)
                return f.read()
        b = http_download_bytes(url)
        try:
            with open(cache_name, "wb") as f:
                f.write(b)
            logger.debug("Cached cover to %s", cache_name)
        except Exception:
            logger.debug("Failed to cache cover %s", cache_name)
        return b
    except Exception as e:
        logger.warning("download_cover failed for %s: %s", url, e)
        return None
