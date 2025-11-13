# epub_enricher/src/epub_enricher/core/epub_metadata.py
"""
Logique métier pour lire et écrire les métadonnées des fichiers EPUB.
"""

import logging
import os
import re
import traceback
from typing import Any, Dict, List, Optional

from ebooklib import epub
from ebooklib.epub import EpubBook, EpubItem
from isbnlib import canonical, is_isbn10, is_isbn13
from langdetect import detect

from epub_enricher.core.models import EpubMeta

from ..config import ISBN_RE

logger = logging.getLogger(__name__)


def safe_read_epub(epub_path: str) -> Optional[EpubBook]:
    """Lit un fichier EPUB de manière sécurisée."""
    try:
        return epub.read_epub(epub_path)
    except Exception as e:
        logger.exception("ebooklib failed to read %s: %s", epub_path, e)
        return None


# --- Fonctions d'extraction (Helpers pour extract_metadata) ---


def _get_metadata_field(book: EpubBook, namespace: str, name: str) -> Optional[Any]:
    """Helper générique pour extraire un champ DC simple."""
    try:
        meta = book.get_metadata(namespace, name)
        if meta:
            return meta[0][0]
    except Exception:
        pass  # Le logging sera fait par l'appelant
    return None


def _get_title(book: EpubBook) -> Optional[str]:
    return _get_metadata_field(book, "DC", "title")


def _get_publisher(book: EpubBook) -> Optional[str]:
    return _get_metadata_field(book, "DC", "publisher")


def _get_date(book: EpubBook) -> Optional[str]:
    return _get_metadata_field(book, "DC", "date")


def _get_summary(book: EpubBook) -> Optional[str]:
    return _get_metadata_field(book, "DC", "description")


def _get_language(book: EpubBook) -> Optional[str]:
    return _get_metadata_field(book, "DC", "language")


def _get_authors(book: EpubBook) -> Optional[List[str]]:
    """Extrait les auteurs."""
    try:
        auths_meta = book.get_metadata("DC", "creator")
        authors = []
        for a in auths_meta:
            authors.append(a[0] if isinstance(a, tuple) else str(a))
        return authors if authors else None
    except Exception:
        return None


def _get_tags(book: EpubBook) -> Optional[List[str]]:
    """Extrait les sujets/tags."""
    try:
        subj_meta = book.get_metadata("DC", "subject")
        return [s[0] for s in subj_meta if s[0]] or None
    except Exception:
        return None


def _get_identifier(book: EpubBook) -> Optional[str]:
    """Extrait l'ISBN canonique des identifiants."""
    try:
        ids_meta = book.get_metadata("DC", "identifier")
        for ident in ids_meta:
            candidate = ident[0]
            if isinstance(candidate, str) and ISBN_RE.search(candidate):
                m = ISBN_RE.search(candidate).group(0)
                if is_isbn10(m) or is_isbn13(m):
                    return canonical(m)
    except Exception:
        return None
    return None


def _find_cover_by_type(book: EpubBook) -> Optional[EpubItem]:
    """Méthode 1 : Chercher un item de type ITEM_COVER."""
    items = list(book.get_items_of_type(epub.ITEM_COVER))
    if items:
        logger.info("Cover found via ITEM_COVER")
        return items[0]
    return None


def _find_cover_by_opf(book: EpubBook) -> Optional[EpubItem]:
    """Méthode 2 : Chercher dans les métadonnées OPF."""
    meta_cover = book.get_metadata("OPF", "cover")
    if meta_cover:
        cover_id = meta_cover[0][1].get("content")
        if cover_id:
            logger.info("Cover found via OPF metadata")
            return book.get_item_with_id(cover_id)
    return None


def _find_cover_by_bruteforce(book: EpubBook) -> Optional[EpubItem]:
    """Méthode 3 : Chercher la première image pertinente."""
    logger.info("Standard cover methods failed. Trying brute-force...")
    images = list(book.get_items_of_type(epub.ITEM_IMAGE))
    if images:
        images.sort(
            key=lambda x: (
                0 if "cover" in x.get_name().lower() else 1 if "couv" in x.get_name().lower() else 2
            )
        )
        logger.info("Cover found via brute-force: %s", images[0].get_name())
        return images[0]
    return None


def _get_cover_data(book: EpubBook, epub_path: str) -> Optional[bytes]:
    """Tente d'extraire la couverture en utilisant plusieurs méthodes."""
    try:
        cover_item = (
            _find_cover_by_type(book) or _find_cover_by_opf(book) or _find_cover_by_bruteforce(book)
        )
        if cover_item:
            logger.info("Cover image data extracted for %s", epub_path)
            return cover_item.get_content()

        logger.info("No cover found for %s", epub_path)
    except Exception:
        logger.info("Could not extract cover image for %s", epub_path)
    return None


def _detect_language_from_text(book: EpubBook) -> Optional[str]:
    """Fallback : Détecte la langue depuis le contenu texte."""
    try:
        docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
        if docs:
            text = docs[0].get_content().decode("utf-8", errors="ignore")
            sample = re.sub("<[^<]+?>", "", text)[:3000]
            if sample.strip():
                return detect(sample)
    except Exception:
        logger.info("Language detection failed.")
    return None


def _find_isbn_in_text(book: EpubBook) -> Optional[str]:
    """Fallback : Cherche un ISBN dans le contenu texte."""
    try:
        for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
            txt = item.get_content().decode("utf-8", errors="ignore")
            m = ISBN_RE.search(txt)
            if m:
                raw = m.group(0)
                if is_isbn10(raw) or is_isbn13(raw):
                    return canonical(raw)
    except Exception:
        logger.info("Text ISBN search failed.")
    return None


def extract_metadata(epub_path: str) -> Dict:
    """Extrait les métadonnées d'un fichier EPUB (fonction principale)."""
    data = {
        k: None
        for k in [
            "title",
            "authors",
            "language",
            "identifier",
            "publisher",
            "date",
            "tags",
            "summary",
            "cover_data",
        ]
    }
    book = safe_read_epub(epub_path)
    if not book:
        return data

    # Extraction principale
    data["title"] = _get_title(book)
    data["authors"] = _get_authors(book)
    data["language"] = _get_language(book)
    data["identifier"] = _get_identifier(book)
    data["publisher"] = _get_publisher(book)
    data["date"] = _get_date(book)
    data["summary"] = _get_summary(book)
    data["tags"] = _get_tags(book)
    data["cover_data"] = _get_cover_data(book, epub_path)

    # Logique de fallback
    if not data["language"]:
        data["language"] = _detect_language_from_text(book)
    if not data["identifier"]:
        data["identifier"] = _find_isbn_in_text(book)

    logger.info("Extracted metadata for %s: ...", epub_path)  # Log abrégé
    return data


# --- Fonctions de mise à jour (Helpers pour update_epub_with_metadata) ---


def _apply_new_metadata(new_book: EpubBook, meta: EpubMeta, old_book: EpubBook):
    """Applique les métadonnées propres de l'objet Meta au nouveau livre."""
    logger.info("Application des métadonnées propres au nouveau livre...")
    if meta.suggested_title:
        new_book.set_title(meta.suggested_title)
    if meta.suggested_isbn:
        new_book.set_identifier(meta.suggested_isbn)

    # Gérer la langue (avec fallback)
    if meta.suggested_language:
        new_book.set_language(meta.suggested_language)
    else:
        old_lang = _get_language(old_book)
        new_book.set_language(old_lang or "und")

    if meta.suggested_authors:
        for a in meta.suggested_authors:
            new_book.add_author(a)
    if meta.suggested_publisher:
        new_book.add_metadata("DC", "publisher", meta.suggested_publisher)
    if meta.suggested_publication_date:
        new_book.add_metadata("DC", "date", meta.suggested_publication_date)
    if meta.suggested_tags:
        for t in meta.suggested_tags:
            new_book.add_metadata("DC", "subject", t)
    if meta.suggested_summary:
        new_book.add_metadata("DC", "description", meta.suggested_summary)


def _copy_items(new_book: EpubBook, old_book: EpubBook, meta: EpubMeta) -> Dict[str, EpubItem]:
    """Copie les items de l'ancien livre vers le nouveau.

    Ignore la navigation et l'ancienne couverture.
    """
    item_map = {}
    for item in old_book.get_items():
        # Ignorer les fichiers de navigation
        if item.file_name.lower() in ("toc.ncx", "nav.xhtml"):
            continue

        # Ignorer l'ancienne couverture si une nouvelle est suggérée
        is_image = item.media_type and item.media_type.startswith("image/")
        is_cover_name = "cover" in item.id.lower() or "cover" in item.file_name.lower()
        if meta.suggested_cover_data and is_image and is_cover_name:
            logger.info("Ignoré l'ancienne cover lors de la copie.")
            continue

        item_map[item.id] = item
        new_book.add_item(item)
    return item_map


def _handle_cover(
    new_book: EpubBook, old_book: EpubBook, meta: EpubMeta, item_map: Dict[str, EpubItem]
):
    """Définit la nouvelle couverture ou conserve l'ancienne."""
    if meta.suggested_cover_data:
        logger.info("Définition de la nouvelle couverture...")
        new_book.set_cover("cover.jpg", meta.suggested_cover_data)
    else:
        # Essayer de conserver l'ancienne
        old_cover_id_meta = old_book.get_metadata("OPF", "cover")
        if old_cover_id_meta:
            cover_id = old_cover_id_meta[0][1].get("content")
            if cover_id in item_map:
                logger.info(f"Conservation de l'ancienne couverture (ID: {cover_id})")
                new_book.metadata["OPF"] = {"cover": [("", {"content": cover_id})]}


def _copy_navigation(new_book: EpubBook, old_book: EpubBook):
    """Copie le spine, la toc, et recrée les items de navigation."""
    new_book.spine = old_book.spine
    new_book.toc = old_book.toc

    logger.info("Création des fichiers de navigation (NCX/NAV)...")
    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())


def _write_rebuilt_epub(book: EpubBook, epub_path: str):
    """Écrit le livre reconstruit de manière sécurisée (via un fichier temporaire)."""
    temp_epub_path = epub_path + ".tmp"
    try:
        epub.write_epub(temp_epub_path, book)
        logger.info("Successfully wrote to temporary file: %s", temp_epub_path)
        os.replace(temp_epub_path, epub_path)
        logger.info("Replaced original file with temporary file.")
    except Exception as write_e:
        logger.exception("Failed during temp write or replace: %s", write_e)
        if os.path.exists(temp_epub_path):
            try:
                os.remove(temp_epub_path)
            except Exception:
                pass
        raise write_e


def update_epub_with_metadata(epub_path: str, meta: "EpubMeta") -> bool:
    """Met à jour un fichier EPUB en le reconstruisant (fonction principale)."""
    logger.info("--- DEBUT UPDATE EPUB (REBUILD MODE) - %s ---", meta.filename)

    try:
        # backup_file(epub_path) # Géré par file_utils maintenant si nécessaire

        # 1. Lire l'ancien livre
        old_book = safe_read_epub(epub_path)
        if not old_book:
            raise ValueError("safe_read_epub a échoué, impossible de continuer.")

        # 2. Créer un nouveau livre et appliquer les métadonnées
        new_book = epub.EpubBook()
        _apply_new_metadata(new_book, meta, old_book)

        # 3. Copier le contenu
        item_map = _copy_items(new_book, old_book, meta)
        _handle_cover(new_book, old_book, meta, item_map)
        _copy_navigation(new_book, old_book)

        # 4. Écrire le nouveau livre
        _write_rebuilt_epub(new_book, epub_path)

        logger.info("REBUILT EPUB %s. SUCCESS.", epub_path)
        return True

    except Exception as e:
        meta.note = f"Error rebuilding epub: {e}\n{traceback.format_exc()}"
        logger.exception("Error rebuilding epub %s", epub_path)
        return False
