# epub_enricher/src/epub_enricher/core/epub_processor.py
"""
Logique métier pour lire et écrire les fichiers EPUB
"""

import logging
import os
import re
import shutil
import time
import traceback
from pathlib import Path
from typing import Dict, List

from ebooklib import epub
from isbnlib import canonical, is_isbn10, is_isbn13
from langdetect import detect

from epub_enricher.core.models import EpubMeta

from ..config import (
    BACKUP_DIR,
    ISBN_RE,
    SUPPORTED_EXT,
    ensure_directories,
)
from .content_analyzer import extract_advanced_metadata

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
    logger.debug("Backed up %s -> %s", path, dst)
    return dst


def safe_read_epub(epub_path: str):
    """Lit un fichier EPUB de manière sécurisée."""
    try:
        return epub.read_epub(epub_path)
    except Exception as e:
        logger.exception("ebooklib failed to read %s: %s", epub_path, e)
        return None


def extract_metadata(epub_path: str) -> Dict:
    """Extrait les métadonnées d'un fichier EPUB, y compris la couverture et l'analyse avancée."""
    data = {
        "title": None,
        "authors": None,
        "language": None,
        "identifier": None,
        "cover_data": None,
    }
    book = safe_read_epub(epub_path)
    if not book:
        return data

    try:
        title = book.get_metadata("DC", "title")
        if title:
            data["title"] = title[0][0]
    except Exception:
        logger.debug("Title not found for %s", epub_path)

    try:
        auths = book.get_metadata("DC", "creator")
        authors = []
        for a in auths:
            if isinstance(a, tuple):
                authors.append(a[0])
            else:
                authors.append(str(a))
        data["authors"] = authors if authors else None
    except Exception:
        logger.debug("Authors not found for %s", epub_path)

    try:
        lang_meta = book.get_metadata("DC", "language")
        if lang_meta:
            data["language"] = lang_meta[0][0]
    except Exception:
        logger.debug("Language metadata not found for %s", epub_path)

    try:
        ids = book.get_metadata("DC", "identifier")
        for ident in ids:
            candidate = ident[0]
            if isinstance(candidate, str) and ISBN_RE.search(candidate):
                m = ISBN_RE.search(candidate).group(0)
                if is_isbn10(m) or is_isbn13(m):
                    data["identifier"] = canonical(m)
                    break
    except Exception:
        logger.debug("Identifier not found for %s", epub_path)

    try:
        cover_item = None
        # Méthode 1 : Chercher un item de type ITEM_COVER
        items = list(book.get_items_of_type(epub.ITEM_COVER))
        if items:
            cover_item = items[0]
            logger.debug("Cover found via ITEM_COVER for %s", epub_path)

        # Méthode 2 : Si la première échoue, chercher dans les métadonnées OPF
        if not cover_item:
            meta_cover = book.get_metadata("OPF", "cover")
            if meta_cover:
                # meta_cover est une liste de tuples, ex: [('x_cover', {'content': 'cover-image'})]
                cover_id = meta_cover[0][1].get("content")
                if cover_id:
                    cover_item = book.get_item_with_id(cover_id)
                    logger.debug("Cover found via OPF metadata for %s", epub_path)

        if cover_item:
            data["cover_data"] = cover_item.get_content()
            logger.debug("Cover image data extracted successfully for %s", epub_path)
        else:
            # NOUVEAU LOG : Indique qu'aucune couverture n'a été trouvée
            logger.info("No standard cover found for %s", epub_path)

    except Exception:
        logger.debug("Could not extract cover image for %s", epub_path)

    if not data["language"]:
        try:
            docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
            if docs:
                text = docs[0].get_content().decode("utf-8", errors="ignore")
                sample = re.sub("<[^<]+?>", "", text)[:3000]
                if sample.strip():
                    data["language"] = detect(sample)
        except Exception:
            logger.debug("Language detection failed for %s", epub_path)

    if not data["identifier"]:
        try:
            for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
                txt = item.get_content().decode("utf-8", errors="ignore")
                m = ISBN_RE.search(txt)
                if m:
                    raw = m.group(0)
                    if is_isbn10(raw) or is_isbn13(raw):
                        data["identifier"] = canonical(raw)
                        break
        except Exception:
            logger.debug("Text ISBN search failed for %s", epub_path)

    # NOUVEAU : Analyse avancée du contenu
    try:
        advanced_data = extract_advanced_metadata(epub_path)
        data.update(advanced_data)
        logger.info(
            (
                "Extracted advanced metadata for %s: "
                "content_isbn=%s, content_genre=%s, content_summary=%s"
            ),
            epub_path,
            advanced_data.get("content_isbn"),
            advanced_data.get("content_genre"),
            "Yes" if advanced_data.get("content_summary") else "No",
        )
    except Exception as e:
        logger.warning("Advanced metadata extraction failed for %s: %s", epub_path, e)

    logger.info(
        "Extracted metadata for %s: title=%s, authors=%s, isbn=%s, lang=%s",
        epub_path,
        data["title"],
        data["authors"],
        data["identifier"],
        data["language"],
    )
    return data


def update_epub_with_metadata(epub_path: str, meta) -> bool:
    """Met à jour un fichier EPUB avec les nouvelles métadonnées."""
    try:
        backup_file(epub_path)
    except Exception as e:
        meta.note = f"Backup failed: {e}"
        logger.exception("Backup failed for %s", epub_path)
        return False

    try:
        book = epub.read_epub(epub_path)

        if meta.suggested_title:
            try:
                book.set_title(meta.suggested_title)
            except Exception:
                logger.exception("Failed to set title for %s", epub_path)

        if meta.suggested_authors:
            try:
                book.del_metadata("DC", "creator")
                for a in meta.suggested_authors:
                    book.add_author(a)
            except Exception:
                logger.exception("Failed to set authors for %s", epub_path)

        if meta.suggested_isbn:
            try:
                book.set_identifier(meta.suggested_isbn)
            except Exception:
                logger.exception("Failed to set identifier for %s", epub_path)

        if meta.suggested_language:
            try:
                book.set_language(meta.suggested_language)
            except Exception:
                logger.exception("Failed to set language for %s", epub_path)

        if meta.suggested_cover_data:
            try:
                book.set_cover("cover.jpg", meta.suggested_cover_data)
            except Exception:
                logger.exception("Failed to set cover for %s", epub_path)

        epub.write_epub(epub_path, book)
        logger.info("Updated EPUB %s with suggested metadata", epub_path)
        return True
    except Exception as e:
        meta.note = f"Error updating epub: {e}\n{traceback.format_exc()}"
        logger.exception("Error updating epub %s", epub_path)
        return False
    """Met à jour un fichier EPUB avec les nouvelles métadonnées."""
    try:
        backup_file(epub_path)
    except Exception as e:
        meta.note = f"Backup failed: {e}"
        logger.exception("Backup failed for %s", epub_path)
        return False

    try:
        book = epub.read_epub(epub_path)

        # Mise à jour du titre
        if meta.suggested_title:
            try:
                book.set_title(meta.suggested_title)
            except Exception:
                logger.exception("Failed to set title for %s", epub_path)

        # Mise à jour des auteurs (efface les anciens et ajoute les nouveaux)
        if meta.suggested_authors:
            try:
                # Retirer les anciens auteurs pour éviter les doublons
                book.del_metadata("DC", "creator")
                for a in meta.suggested_authors:
                    book.add_author(a)
            except Exception:
                logger.exception("Failed to set authors for %s", epub_path)

        # Mise à jour de l'identifiant (ISBN)
        if meta.suggested_isbn:
            try:
                book.set_identifier(meta.suggested_isbn)
            except Exception:
                logger.exception("Failed to set identifier for %s", epub_path)

        # Mise à jour de la langue
        if meta.suggested_language:
            try:
                book.set_language(meta.suggested_language)
            except Exception:
                logger.exception("Failed to set language for %s", epub_path)

        # MODIFIÉ : La logique de mise à jour de la couverture utilise les données binaires
        # stockées dans meta.suggested_cover_data, au lieu de télécharger l'image.
        if meta.suggested_cover_data:
            try:
                # On utilise directement les bytes de l'image
                book.set_cover("cover.jpg", meta.suggested_cover_data)
            except Exception:
                logger.exception("Failed to set cover for %s", epub_path)

        epub.write_epub(epub_path, book)
        logger.info("Updated EPUB %s with suggested metadata", epub_path)
        return True
    except Exception as e:
        meta.note = f"Error updating epub: {e}\n{traceback.format_exc()}"
        logger.exception("Error updating epub %s", epub_path)
        return False


def sanitize_filename(value: str) -> str:
    """Nettoie un texte pour un nom de fichier valide."""
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def rename_epub_file(meta: "EpubMeta") -> None:
    """Renomme le fichier EPUB en fonction des métadonnées."""
    try:
        epub_path = Path(meta.path)
        folder = epub_path.parent

        # Priorité : métadonnées suggérées > originales
        year_raw = meta.suggested_publication_date or meta.original_publication_date or "unknown"
        authors = meta.suggested_authors or meta.original_authors or "Unknown"
        title = meta.suggested_title or meta.original_title or epub_path.stem

        # Conversion si liste d’auteurs
        if isinstance(authors, list):
            authors = ", ".join(authors[:2])  # on limite à 2 pour éviter les noms trop longs

        # Nettoyage des champs
        authors = sanitize_filename(authors)
        title = sanitize_filename(title)

        # NOUVEAU: Gérer l'année de manière optionnelle
        year_part = ""
        if year_raw:
            year = sanitize_filename(str(year_raw))
            year_part = f"{year} - "

        # Construction du nouveau nom
        new_name = f"{year_part}{authors} - {title}.epub"
        new_path = folder / new_name

        # Éviter les collisions
        counter = 1
        while new_path.exists():
            new_path = folder / f"{year} - {authors} - {title} ({counter}).epub"
            counter += 1

        # Renommage
        epub_path.rename(new_path)

        # Mettre à jour le modèle
        meta.path = str(new_path)
        meta.filename = new_name

        logger.info("Renamed EPUB: %s -> %s", epub_path.name, new_name)
    except Exception as e:
        logger.warning("Failed to rename EPUB %s: %s", meta.filename, e)
