# epub_enricher/src/epub_enricher/gui/task_manager.py
"""
Gestionnaire des tâches de fond (threading) pour l'interface graphique.
Sépare la logique de fetch et d'application de l'orchestrateur GUI.
"""

import logging
import threading
from typing import TYPE_CHECKING, Dict, List

from ..core.epub_processor import rename_epub_file, update_epub_with_metadata
from ..core.metadata_fetcher import download_cover, fetch_genre_and_summary, query_openlibrary_full
from . import helpers

if TYPE_CHECKING:
    from ..core.models import EpubMeta
    from .main_window import EnricherGUI

logger = logging.getLogger(__name__)

# --- TÂCHE DE FETCH ---


def start_fetch_task(app: "EnricherGUI", selection: List[str]):
    """Lance le thread de recherche de suggestions."""
    threading.Thread(target=_fetch_worker, args=(app, selection), daemon=True).start()


def _fetch_worker(app: "EnricherGUI", selection: List[str]):
    """Logique exécutée dans le thread de recherche."""
    changed = False
    for s in selection:
        idx = int(s)
        meta = app.meta_list[idx]
        try:
            # 1. Fetch OpenLibrary (Titre, Auteur, ISBN, etc.)
            # MODIFIÉ : _fetch_openlibrary_data stocke maintenant les éditions
            _fetch_openlibrary_data(meta)

            # 2. Fetch Genre & Summary (API séparée)
            _fetch_genre_summary_data(meta)

            # 3. Download Cover (si URL trouvée)
            _download_cover_data(meta)

            meta.processed = True
            meta.note = "Suggestion fetched"
            changed = True
            logger.debug("Fetched suggestion for %s", meta.filename)

        except Exception as e:
            meta.note = f"Fetch error: {e}"
            logger.exception("Fetch suggestions error for %s", meta.filename)

    if changed:
        # Demander à la GUI de se rafraîchir
        app.after(0, app.schedule_gui_refresh)


def _fetch_openlibrary_data(meta: "EpubMeta") -> Dict:
    """Sous-méthode pour le fetch OpenLibrary."""
    res = query_openlibrary_full(
        title=meta.original_title,
        authors=meta.original_authors,
        isbn=meta.original_isbn,
    )

    # Stocker toutes les éditions trouvées dans le modèle
    meta.found_editions = res.get("related_docs", [])

    suggested = res.get("by_isbn") or (res.get("related_docs") or [{}])[0]

    meta.suggested_title = suggested.get("title")
    meta.suggested_authors = suggested.get("authors") or suggested.get("author_name")
    meta.suggested_isbn = suggested.get("isbn")
    meta.suggested_language = suggested.get("language")
    meta.suggested_publisher = suggested.get("publisher")
    meta.suggested_publication_date = suggested.get("publish_date") or suggested.get(
        "first_publish_year"
    )
    meta.suggested_tags = suggested.get("subject") or []
    meta.suggested_cover_url = suggested.get("cover")

    return res


def _fetch_genre_summary_data(meta: "EpubMeta"):
    """Sous-méthode pour le fetch Genre/Résumé."""
    try:
        data = fetch_genre_and_summary(
            title=meta.original_title,
            authors=meta.original_authors,
            isbn=meta.original_isbn,
        )
        if data.get("genre"):
            meta.suggested_genre = data["genre"]
        if data.get("summary"):
            meta.suggested_summary = data["summary"]
    except Exception as e:
        logger.warning("Failed to fetch genre and summary for %s: %s", meta.filename, e)


def _download_cover_data(meta: "EpubMeta"):
    """Sous-méthode pour le téléchargement de la couverture."""
    meta.suggested_cover_data = None
    if meta.suggested_cover_url:
        try:
            meta.suggested_cover_data = download_cover(meta.suggested_cover_url)
        except Exception:
            logger.exception("Failed to download cover")


# --- TÂCHE D'APPLICATION ---
def start_apply_task(app: "EnricherGUI", metas: List["EpubMeta"]):
    """Lance le thread d'application des modifications."""
    threading.Thread(target=_apply_worker, args=(app, metas), daemon=True).start()


def _apply_worker(app: "EnricherGUI", metas: List["EpubMeta"]):
    """Logique exécutée dans le thread d'application."""
    any_changed = False
    for m in metas:
        try:
            # Note: update_epub_with_metadata utilise les champs 'suggested_'
            # (que nous traitons comme 'final') pour l'écriture. C'est correct.
            success = update_epub_with_metadata(m.path, m)
            if success:
                m.note = "Updated"
                # Utiliser l'helper pour copier 'suggested' -> 'original'
                helpers.apply_suggestions_to_model(m)
                # Utiliser l'helper pour nettoyer le modèle (y compris 'processed')
                helpers.reset_suggestions_on_model(m)
                rename_epub_file(m)
                any_changed = True
            else:
                m.note = m.note or "Failed"
        except Exception as e:
            m.note = f"Error applying: {e}"
            logger.exception("Apply accepted failed for %s", m.filename)

    if any_changed:
        # Demander à la GUI de se rafraîchir
        app.after(0, app.schedule_gui_refresh)
        app.after(
            0,
            lambda: app.show_info_message(
                "Done", "Changes applied (check backup folder if needed)"
            ),
        )
