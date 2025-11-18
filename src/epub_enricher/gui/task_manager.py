# epub_enricher/src/epub_enricher/gui/task_manager.py
"""
Gestionnaire des tâches de fond (threading) pour l'interface graphique.
Logique de fetch et d'application découplée de l'UI.
"""

import logging
import threading
from typing import TYPE_CHECKING, Callable, Dict, List

from ..core.epub import update_epub_with_metadata
from ..core.file_utils import rename_epub_file
from ..core.metadata_fetcher import download_cover, query_openlibrary_full
from . import helpers

if TYPE_CHECKING:
    from ..core.models import EpubMeta

logger = logging.getLogger(__name__)

# --- TÂCHE DE FETCH ---


def start_fetch_task(metas_to_fetch: List["EpubMeta"], on_complete: Callable[[], None]):
    """Lance le thread de recherche de suggestions."""
    logger.debug(f"Démarrage du Fetch Task pour {len(metas_to_fetch)} items.")
    threading.Thread(target=_fetch_worker, args=(metas_to_fetch, on_complete), daemon=True).start()


def _fetch_worker(metas: List["EpubMeta"], on_complete: Callable[[], None]):
    """Logique exécutée dans le thread de recherche."""
    changed = False
    for meta in metas:
        try:
            # 1. Fetch OpenLibrary
            _fetch_openlibrary_data(meta)

            # 2. Download Cover (si URL trouvée)
            _download_cover_data(meta)

            meta.processed = True
            meta.note = "Suggestion fetched"
            changed = True
            logger.debug("Fetched suggestion for %s", meta.filename)

        except Exception as e:
            meta.note = f"Fetch error: {e}"
            logger.exception("Fetch suggestions error for %s", meta.filename)

    if changed:
        # Signaler à l'appelant (l'UI) que la tâche est terminée
        on_complete()


def _fetch_openlibrary_data(meta: "EpubMeta") -> Dict:
    """Sous-méthode pour le fetch OpenLibrary."""
    res = query_openlibrary_full(
        title=meta.original_title,
        authors=meta.original_authors,
        isbn=meta.original_isbn,
    )

    # Stocker toutes les éditions trouvées dans le modèle
    meta.found_editions = res.get("related_docs", [])
    return res


def _download_cover_data(meta: "EpubMeta"):
    """Sous-méthode pour le téléchargement de la couverture."""
    cover_id_or_url = meta.suggested_cover_data
    meta.suggested_cover_data = None  # Effacer l'ID/URL

    if cover_id_or_url:
        try:
            # Stocker les données binaires
            meta.suggested_cover_data = download_cover(cover_id_or_url)
        except Exception:
            logger.exception("Failed to download cover")


# --- TÂCHE DE TÉLÉCHARGEMENT DE COUVERTURE (SÉPARÉE) ---


def start_cover_download_task(meta: "EpubMeta", on_complete: Callable[[], None]):
    """Lance un thread dédié juste pour télécharger une couverture."""
    logger.debug(f"Démarrage du Download Cover Task pour {meta.filename}.")
    threading.Thread(target=_cover_download_worker, args=(meta, on_complete), daemon=True).start()


def _cover_download_worker(meta: "EpubMeta", on_complete: Callable[[], None]):
    """Worker pour télécharger une seule couverture."""
    try:
        _download_cover_data(meta)
        logger.debug(f"Couverture téléchargée pour {meta.filename}")
    except Exception as e:
        logger.error(f"Échec du téléchargement de la couverture pour {meta.filename}: {e}")
    finally:
        # Toujours appeler on_complete pour rafraîchir l'UI
        on_complete()


# --- TÂCHE D'APPLICATION ---
def start_apply_task(
    metas: List["EpubMeta"],
    on_complete: Callable[[], None],
    on_success_message: Callable[[str], None],
):
    """Lance le thread d'application des modifications."""
    logger.debug(f"Démarrage du Apply Task pour {len(metas)} items.")
    threading.Thread(
        target=_apply_worker, args=(metas, on_complete, on_success_message), daemon=True
    ).start()


def _apply_worker(
    metas: List["EpubMeta"],
    on_complete: Callable[[], None],
    on_success_message: Callable[[str], None],
):
    """Logique exécutée dans le thread d'application."""
    any_changed = False
    for m in metas:
        success = _apply_single_meta(m)
        if success:
            any_changed = True

    if any_changed:
        # Signaler la complétion
        on_complete()
        # Demander l'affichage d'un message de succès
        on_success_message("Changes applied (check backup folder if needed)")


def _apply_single_meta(m: "EpubMeta") -> bool:
    """Tente d'appliquer les modifications à un seul fichier EPUB."""
    try:
        success = update_epub_with_metadata(m.path, m)
        if success:
            m.note = "Updated"
            helpers.apply_suggestions_to_model(m)
            helpers.reset_suggestions_on_model(m)
            rename_epub_file(m)
            return True
        else:
            m.note = m.note or "Failed"
            return False
    except Exception as e:
        m.note = f"Error applying: {e}"
        logger.exception("Apply accepted failed for %s", m.filename)
        return False
