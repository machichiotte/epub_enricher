# epub_enricher/src/epub_enricher/core/network_utils.py
"""
Utilitaires réseau génériques (retry backoff, requêtes HTTP).
"""

import logging
import random
import time
from functools import wraps
from typing import Callable, Dict, Optional

import requests

from ..config import (
    API_TIMEOUT,
    INITIAL_BACKOFF,
    JITTER,
    MAX_BACKOFF,
    MAX_RETRIES,
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
