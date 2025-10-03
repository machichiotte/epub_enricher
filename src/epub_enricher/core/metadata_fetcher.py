# epub_enricher/src/epub_enricher/core/metadata_fetcher.py
"""
Logique pour interroger les APIs (OpenLibrary) et récupérer les métadonnées
"""

import hashlib
import logging
import os
import random
import time
from functools import wraps
from typing import Callable, Dict, List, Optional

import requests
from isbnlib import canonical, is_isbn10, is_isbn13

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


def query_openlibrary_search(title: str, author: Optional[str] = None) -> Optional[Dict]:
    """Interroge OpenLibrary avec un titre et auteur pour récupérer les métadonnées."""
    try:
        q = title
        if author:
            q += f" {author}"
        params = {"q": q, "title": title}
        r = http_get(OPENLIB_SEARCH, params=params)
        js = r.json()
        docs = js.get("docs")
        if docs:
            logger.info("OpenLibrary search returned %d docs for query %s", len(docs), q)
            return docs[0]
    except Exception as e:
        logger.warning("query_openlibrary_search failed for %s / %s: %s", title, author, e)
    return None


def extract_suggested_from_openlib(
    isbn: Optional[str], title: Optional[str], authors: Optional[List[str]]
) -> Dict:
    """Extrait les métadonnées suggérées depuis OpenLibrary."""
    out = {}
    if isbn:
        data = query_openlibrary_by_isbn(isbn)
        if data:
            out["title"] = data.get("title")
            out["authors"] = (
                [a.get("name") for a in data.get("authors", [])] if data.get("authors") else None
            )
            out["isbn"] = isbn
            cover = data.get("cover")
            if cover:
                out["cover"] = cover.get("large") or cover.get("medium") or cover.get("small")
            languages = data.get("languages")
            if languages and isinstance(languages, list):
                lang_keys = [lang.get("key") for lang in languages if isinstance(lang, dict)]
                if lang_keys:
                    out["language"] = lang_keys[0].split("/")[-1]
            return out
    if title:
        auth = authors[0] if authors else None
        doc = query_openlibrary_search(title, auth)
        if doc:
            out["title"] = doc.get("title")
            out["authors"] = doc.get("author_name")
            isbns = doc.get("isbn")
            if isbns:
                for candidate in isbns:
                    if is_isbn13(candidate) or is_isbn10(candidate):
                        try:
                            out["isbn"] = canonical(candidate)
                            break
                        except Exception:
                            out["isbn"] = candidate
            cover_id = doc.get("cover_i")
            if cover_id:
                out["cover"] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
            out["language"] = doc.get("language")[0] if doc.get("language") else None
            return out
    return out


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
