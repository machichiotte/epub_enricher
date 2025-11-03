# epub_enricher/src/epub_enricher/gui/helpers.py
"""
Fonctions utilitaires et de manipulation du modèle de données pour l'interface graphique.
"""

import csv
import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..core.models import EpubMeta

logger = logging.getLogger(__name__)


def calculate_metadata_quality(meta: "EpubMeta") -> int:
    """Calcule un score de qualité des métadonnées (0-100%)."""
    score = 0

    # Champs où 'suggested' ou 'original' comptent pour 1 point
    FIELDS_TO_SCORE = [
        "title",
        "authors",
        "publisher",
        "isbn",
        "language",
        "publication_date",
        "tags",
    ]

    for field in FIELDS_TO_SCORE:
        if getattr(meta, f"suggested_{field}") or getattr(meta, f"original_{field}"):
            score += 1

    # Cas spéciaux pour genre et résumé
    if meta.suggested_genre or meta.content_genre or meta.original_tags:
        score += 1
    if meta.suggested_summary or meta.content_summary:
        score += 1

    total_fields = len(FIELDS_TO_SCORE) + 2  # 7 champs + genre + résumé = 9
    return int((score / total_fields) * 100)


def apply_suggestions_to_model(m: "EpubMeta"):
    """Applique les suggestions au modèle original."""
    m.original_title = m.suggested_title or m.original_title
    m.original_authors = m.suggested_authors or m.original_authors
    m.original_isbn = m.suggested_isbn or m.original_isbn
    m.original_language = m.suggested_language or m.original_language
    m.original_tags = m.suggested_tags or m.original_tags
    m.original_publisher = m.suggested_publisher or m.original_publisher
    m.original_publication_date = m.suggested_publication_date or m.original_publication_date
    if m.suggested_cover_data:
        m.original_cover_data = m.suggested_cover_data
    if m.suggested_genre:
        m.content_genre = m.suggested_genre
    if m.suggested_summary:
        m.content_summary = m.suggested_summary


def reset_suggestions_on_model(m: "EpubMeta"):
    """Réinitialise tous les champs 'suggested' et l'état."""
    m.suggested_title = None
    m.suggested_authors = []
    m.suggested_isbn = None
    m.suggested_language = None
    m.suggested_tags = []
    m.suggested_publisher = None
    m.suggested_publication_date = None
    m.suggested_cover_url = None
    m.suggested_cover_data = None
    m.suggested_genre = None
    m.suggested_summary = None
    m.accepted = False  # Nettoyage
    m.processed = False  # Réinitialise aussi le statut 'fetched'
    m.found_editions = []  # Vide la liste des éditions
    m.note = ""


def export_to_csv(filepath: str, meta_list: List["EpubMeta"]):
    """Exporte la liste des métadonnées vers un fichier CSV."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "filename",
                    "path",
                    "orig_title",
                    "orig_authors",
                    "orig_tags",
                    "orig_publisher",
                    "orig_date",
                    "orig_isbn",
                    "orig_lang",
                    "content_genre",
                    "content_summary",
                    "sugg_title",
                    "sugg_authors",
                    "sugg_tags",
                    "sugg_publisher",
                    "sugg_date",
                    "sugg_isbn",
                    "sugg_lang",
                    "sugg_genre",
                    "sugg_summary",
                    "accepted",
                    "processed",
                    "note",
                ]
            )
            for m in meta_list:
                w.writerow(
                    [
                        m.filename,
                        m.path,
                        m.original_title,
                        ";".join(m.original_authors or []),
                        ";".join(m.original_tags or []),
                        m.original_publisher,
                        m.original_publication_date,
                        m.original_isbn,
                        m.original_language,
                        m.content_genre or "",
                        m.content_summary or "",
                        m.suggested_title,
                        ";".join(m.suggested_authors or []),
                        ";".join(m.suggested_tags or []),
                        m.suggested_publisher,
                        m.suggested_publication_date,
                        m.suggested_isbn,
                        m.suggested_language,
                        m.suggested_genre or "",
                        m.suggested_summary or "",
                        m.accepted,
                        m.processed,
                        m.note,
                    ]
                )
        logger.info(f"Export CSV réussi vers {filepath}")
    except Exception:
        logger.exception(f"Échec de l'export CSV vers {filepath}")
        raise  # Permet à l'appelant (GUI) de gérer l'erreur
