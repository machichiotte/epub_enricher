# epub_enricher/src/epub_enricher/core/file_utils.py
"""
Logique pour les opérations sur le système de fichiers (trouver, sauvegarder, renommer).
"""

import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List

from ..config import BACKUP_DIR, SUPPORTED_EXT, ensure_directories
from .models import EpubMeta  # Importation du modèle

logger = logging.getLogger(__name__)


def find_epubs_in_folder(folder: str) -> List[str]:
    """Trouve tous les fichiers EPUB dans un dossier et ses sous-dossiers."""
    files = []
    for root, _, filenames in os.walk(folder):
        for f in filenames:
            if f.lower().endswith(SUPPORTED_EXT):
                files.append(os.path.join(root, f))
    logger.info("Found %d epub(s) in folder %s", len(files), folder)
    return files


def backup_file(path: str) -> str:
    """Crée une sauvegarde d'un fichier avec timestamp."""
    ensure_directories()
    basename = os.path.basename(path)
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"{ts}-{basename}")
    shutil.copy2(path, dst)
    logger.info("Backed up %s -> %s", path, dst)
    return dst


def sanitize_filename(value: str) -> str:
    """Nettoie un texte pour un nom de fichier valide."""
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _get_filename_parts(meta: "EpubMeta") -> Dict[str, str]:
    """Extrait et nettoie les composants du nom de fichier depuis les métadonnées."""
    epub_path = Path(meta.path)

    # Priorité : métadonnées suggérées > originales
    year_raw = meta.suggested_publication_date or meta.original_publication_date
    authors_raw = meta.suggested_authors or meta.original_authors or "Unknown"
    title_raw = meta.suggested_title or meta.original_title or epub_path.stem

    # Conversion si liste d’auteurs
    if isinstance(authors_raw, list):
        authors_str = ", ".join(authors_raw[:2])  # Limite à 2 auteurs
    else:
        authors_str = str(authors_raw)

    return {
        "year": sanitize_filename(str(year_raw)) if year_raw else None,
        "authors": sanitize_filename(authors_str),
        "title": sanitize_filename(title_raw),
    }


def _resolve_filename_collision(folder: Path, base_name_parts: Dict[str, str]) -> Path:
    """Génère un chemin final, en évitant les collisions."""
    year_part = f"{base_name_parts['year']} - " if base_name_parts["year"] else ""
    authors = base_name_parts["authors"]
    title = base_name_parts["title"]

    new_name = f"{year_part}{authors} - {title}.epub"
    new_path = folder / new_name

    # Gérer les collisions
    counter = 1
    while new_path.exists():
        new_name = f"{year_part}{authors} - {title} ({counter}).epub"
        new_path = folder / new_name
        counter += 1

    return new_path, new_name


def rename_epub_file(meta: "EpubMeta") -> None:
    """Renomme le fichier EPUB en fonction des métadonnées."""
    try:
        epub_path = Path(meta.path)
        folder = epub_path.parent

        # 1. Obtenir les composants nettoyés
        parts = _get_filename_parts(meta)

        # 2. Résoudre les collisions et obtenir le chemin/nom final
        new_path, new_name = _resolve_filename_collision(folder, parts)

        # 3. Renommer
        epub_path.rename(new_path)

        # 4. Mettre à jour le modèle
        meta.path = str(new_path)
        meta.filename = new_name

        logger.info("Renamed EPUB: %s -> %s", epub_path.name, new_name)
    except Exception as e:
        logger.warning("Failed to rename EPUB %s: %s", meta.filename, e)
