# epub_enricher/src/epub_enricher/core/models.py
from dataclasses import dataclass, field
from typing import List


@dataclass
class EpubMeta:
    """Modèle de données pour les métadonnées d'un fichier EPUB."""

    path: str
    filename: str

    # Métadonnées originales (lues depuis le fichier)
    original_title: str | None = None
    original_authors: List[str] | None = field(default_factory=list)
    original_isbn: str | None = None
    original_language: str | None = None
    original_publisher: str | None = None
    original_publication_date: str | None = None
    original_tags: List[str] | None = field(default_factory=list)
    original_cover_data: bytes | None = None

    # Métadonnées suggérées / à appliquer
    suggested_title: str | None = None
    suggested_authors: List[str] | None = field(default_factory=list)
    suggested_isbn: str | None = None
    suggested_language: str | None = None
    suggested_publisher: str | None = None
    suggested_publication_date: str | None = None
    suggested_tags: List[str] | None = field(default_factory=list)
    suggested_cover_data: bytes | None = None

    # Statut du traitement
    processed: bool = False
    accepted: bool = False
    note: str = ""
