# epub_enricher/src/epub_enricher/core/epub/writer.py
"""
Module d'écriture EPUB.

Responsabilité unique: Écrire les métadonnées dans les fichiers EPUB
en reconstruisant le fichier de manière propre.
"""

import logging
import os
import traceback
from typing import TYPE_CHECKING, Dict

from ebooklib import epub
from ebooklib.epub import EpubBook, EpubItem

from .reader import _get_language, safe_read_epub

if TYPE_CHECKING:
    from ..models import EpubMeta

logger = logging.getLogger(__name__)


# --- Helpers pour la reconstruction EPUB ---


def _apply_new_metadata(new_book: EpubBook, meta: "EpubMeta", old_book: EpubBook):
    """
    Applique les métadonnées de l'objet Meta au nouveau livre.
    
    Args:
        new_book: Nouveau livre EPUB (vide)
        meta: Objet contenant les métadonnées suggérées
        old_book: Livre EPUB original (pour fallback)
    """
    logger.info("Application des métadonnées propres au nouveau livre...")
    
    if meta.suggested_title:
        new_book.set_title(meta.suggested_title)
        
    if meta.suggested_isbn:
        new_book.set_identifier(meta.suggested_isbn)

    # Gérer la langue (avec fallback sur l'ancien livre)
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


def _copy_items(new_book: EpubBook, old_book: EpubBook, meta: "EpubMeta") -> Dict[str, EpubItem]:
    """
    Copie les items de l'ancien livre vers le nouveau.
    
    Ignore les fichiers de navigation (toc.ncx, nav.xhtml) et
    l'ancienne couverture si une nouvelle est fournie.
    
    Args:
        new_book: Nouveau livre EPUB
        old_book: Livre EPUB original
        meta: Métadonnées (pour vérifier si nouvelle couverture)
        
    Returns:
        Dictionnaire {item_id: item} des items copiés
    """
    item_map = {}
    
    for item in old_book.get_items():
        # Ignorer les fichiers de navigation (seront recréés)
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
    new_book: EpubBook, old_book: EpubBook, meta: "EpubMeta", item_map: Dict[str, EpubItem]
):
    """
    Définit la nouvelle couverture ou conserve l'ancienne.
    
    Args:
        new_book: Nouveau livre EPUB
        old_book: Livre EPUB original
        meta: Métadonnées (pour vérifier nouvelle couverture)
        item_map: Dictionnaire des items copiés
    """
    if meta.suggested_cover_data:
        logger.info("Définition de la nouvelle couverture...")
        new_book.set_cover("cover.jpg", meta.suggested_cover_data)
    else:
        # Essayer de conserver l'ancienne couverture
        old_cover_id_meta = old_book.get_metadata("OPF", "cover")
        if old_cover_id_meta:
            cover_id = old_cover_id_meta[0][1].get("content")
            if cover_id in item_map:
                logger.info(f"Conservation de l'ancienne couverture (ID: {cover_id})")
                new_book.metadata["OPF"] = {"cover": [("", {"content": cover_id})]}


def _copy_navigation(new_book: EpubBook, old_book: EpubBook):
    """
    Copie la navigation et recrée les items de navigation.
    
    Args:
        new_book: Nouveau livre EPUB
        old_book: Livre EPUB original
    """
    new_book.spine = old_book.spine
    new_book.toc = old_book.toc

    logger.info("Création des fichiers de navigation (NCX/NAV)...")
    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())


def _write_rebuilt_epub(book: EpubBook, epub_path: str):
    """
    Écrit le livre reconstruit de manière sécurisée.
    
    Utilise un fichier temporaire pour éviter la corruption en cas d'échec.
    
    Args:
        book: Livre EPUB à écrire
        epub_path: Chemin de destination
        
    Raises:
        Exception: Si l'écriture échoue
    """
    temp_epub_path = epub_path + ".tmp"
    
    try:
        epub.write_epub(temp_epub_path, book)
        logger.info("Successfully wrote to temporary file: %s", temp_epub_path)
        
        # Remplacer atomiquement l'ancien fichier
        os.replace(temp_epub_path, epub_path)
        logger.info("Replaced original file with temporary file.")
        
    except Exception as write_e:
        logger.exception("Failed during temp write or replace: %s", write_e)
        
        # Nettoyer le fichier temporaire en cas d'échec
        if os.path.exists(temp_epub_path):
            try:
                os.remove(temp_epub_path)
            except Exception:
                pass
                
        raise write_e


# --- Fonction principale d'écriture ---


def update_epub_with_metadata(epub_path: str, meta: "EpubMeta") -> bool:
    """
    Met à jour un fichier EPUB en le reconstruisant complètement.
    
    Cette fonction applique les métadonnées suggérées stockées dans
    l'objet meta en reconstruisant entièrement le fichier EPUB.
    Ce mode "rebuild" garantit des métadonnées propres et sans corruption.
    
    Args:
        epub_path: Chemin vers le fichier EPUB à modifier
        meta: Objet EpubMeta contenant les métadonnées suggérées
        
    Returns:
        True si succès, False sinon
        
    Note:
        En cas d'échec, meta.note sera rempli avec l'erreur détaillée
    """
    logger.info("--- DEBUT UPDATE EPUB (REBUILD MODE) - %s ---", meta.filename)

    try:
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
