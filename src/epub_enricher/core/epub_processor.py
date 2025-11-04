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
        "publisher": None,
        "date": None,
        "tags": None,
        "summary": None,
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
        logger.info("Title not found for %s", epub_path)

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
        logger.info("Authors not found for %s", epub_path)

    try:
        lang_meta = book.get_metadata("DC", "language")
        if lang_meta:
            data["language"] = lang_meta[0][0]
    except Exception:
        logger.info("Language metadata not found for %s", epub_path)

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
        logger.info("Identifier not found for %s", epub_path)

    try:
        pub = book.get_metadata("DC", "publisher")
        if pub:
            data["publisher"] = pub[0][0]
    except Exception:
        logger.info("Publisher not found for %s", epub_path)

    try:
        date = book.get_metadata("DC", "date")
        if date:
            data["date"] = date[0][0]
    except Exception:
        logger.info("Date not found for %s", epub_path)

    try:
        desc = book.get_metadata("DC", "description")
        if desc:
            data["summary"] = desc[0][0]
    except Exception:
        logger.info("Description (summary) not found for %s", epub_path)

    try:
        subj = book.get_metadata("DC", "subject")
        if subj:
            # Récupère tous les sujets/tags
            data["tags"] = [s[0] for s in subj if s[0]]
    except Exception:
        logger.info("Subjects (tags) not found for %s", epub_path)

    try:
        cover_item = None
        # Méthode 1 : Chercher un item de type ITEM_COVER
        items = list(book.get_items_of_type(epub.ITEM_COVER))
        if items:
            cover_item = items[0]
            logger.info("Cover found via ITEM_COVER for %s", epub_path)

        # Méthode 2 : Si la première échoue, chercher dans les métadonnées OPF
        if not cover_item:
            meta_cover = book.get_metadata("OPF", "cover")
            if meta_cover:
                # meta_cover est une liste de tuples, ex: [('x_cover', {'content': 'cover-image'})]
                cover_id = meta_cover[0][1].get("content")
                if cover_id:
                    cover_item = book.get_item_with_id(cover_id)
                    logger.info("Cover found via OPF metadata for %s", epub_path)

        # MÉTHODE 3 (BRUTE-FORCE) : Si toujours rien, chercher la 1ère image
        if not cover_item:
            logger.info("Standard cover methods failed. Trying brute-force image search...")
            images = list(book.get_items_of_type(epub.ITEM_IMAGE))
            if images:
                # On trie pour prioriser les noms évidents
                images.sort(
                    key=lambda x: (
                        0
                        if "cover" in x.get_name().lower()
                        else 1 if "couv" in x.get_name().lower() else 2
                    )
                )
                cover_item = images[0]  # On prend la meilleure correspondance
                logger.info("Cover found via brute-force: %s", cover_item.get_name())

        if cover_item:
            data["cover_data"] = cover_item.get_content()
            logger.info("Cover image data extracted successfully for %s", epub_path)
        else:
            logger.info("No cover found (standard or brute-force) for %s", epub_path)

    except Exception:
        logger.info("Could not extract cover image for %s", epub_path)

    if not data["language"]:
        try:
            docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
            if docs:
                text = docs[0].get_content().decode("utf-8", errors="ignore")
                sample = re.sub("<[^<]+?>", "", text)[:3000]
                if sample.strip():
                    data["language"] = detect(sample)
        except Exception:
            logger.info("Language detection failed for %s", epub_path)

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
            logger.info("Text ISBN search failed for %s", epub_path)

    logger.info(
        "Extracted metadata for %s: title=%s, authors=%s, isbn=%s, "
        "lang=%s, date=%s, publisher=%s, tags=%s, summary=%s",
        epub_path,
        data["title"],
        data["authors"],
        data["identifier"],
        data["language"],
        data["date"],
        data["publisher"],
        data["tags"],
        data["summary"],
    )
    return data


def update_epub_with_metadata(epub_path: str, meta: "EpubMeta") -> bool:
    """
    Met à jour un fichier EPUB en RECONSTRUISANT le livre pour garantir l'élimination
    des métadonnées corrompues, tout en utilisant des vérifications génériques
    pour éviter les problèmes de constantes manquantes (ITEM_COVER, ITEM_NCX, etc.).
    """
    logger.info("--- DEBUT UPDATE EPUB (REBUILD MODE) ---")
    logger.info("--- FILENAME %s ---", meta.filename)

    try:
        # Assurez-vous que la fonction backup_file est disponible
        # backup_file(epub_path)
        pass
    except Exception as e:
        meta.note = f"Backup failed: {e}"
        logger.exception("Backup failed for %s", epub_path)
        return False

    try:
        # 1. Lire le vieux livre (corrompu)
        old_book = epub.read_epub(epub_path)
        logger.info("Lu le fichier EPUB original.")

        # 2. Créer un NOUVEAU livre
        new_book = epub.EpubBook()

        # 3. Appliquer SEULEMENT les nouvelles métadonnées au NOUVEAU livre
        logger.info("Application des métadonnées propres au nouveau livre...")

        if meta.suggested_title:
            new_book.set_title(meta.suggested_title)

        if meta.suggested_isbn:
            new_book.set_identifier(meta.suggested_isbn)

        if meta.suggested_language:
            new_book.set_language(meta.suggested_language)
        else:
            old_lang = old_book.get_metadata("DC", "language")
            if old_lang:
                new_book.set_language(old_lang[0][0])
            else:
                new_book.set_language("und")

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

        # 4. Copier tout le *contenu* (items, spine, toc) de l'ancien livre
        logger.info("Copie du contenu (items, spine, toc)...")

        item_map = {}
        for item in old_book.get_items():
            # 1. Ignorer les fichiers de navigation (toc.ncx et nav.xhtml)
            is_navigation_file = item.file_name.lower() in ("toc.ncx", "nav.xhtml")
            if is_navigation_file:
                continue

            # 2. Ignorer l'ancienne couverture si une nouvelle est suggérée
            # FIX: Vérifie le type MIME au lieu de epub.ITEM_IMAGE
            is_image = item.media_type and item.media_type.startswith("image/")
            is_cover_name = "cover" in item.id.lower() or "cover" in item.file_name.lower()

            is_old_cover_image = is_image and is_cover_name

            if meta.suggested_cover_data and is_old_cover_image:
                logger.info("Ignoré l'ancienne cover lors de la copie du contenu.")
                continue

            item_map[item.id] = item
            new_book.add_item(item)

        # Gérer la couverture
        if meta.suggested_cover_data:
            logger.info("Définition de la nouvelle couverture...")
            # La méthode set_cover gère l'ajout de l'item 'cover.jpg'
            new_book.set_cover("cover.jpg", meta.suggested_cover_data)
        else:
            # Si on n'a pas de nouvelle cover, on essaie de garder l'ancienne
            old_cover_id = old_book.get_metadata("OPF", "cover")
            if old_cover_id and old_cover_id[0][1].get("content") in item_map:
                cover_item_id = old_cover_id[0][1].get("content")
                logger.info(f"Conservation de l'ancienne couverture (ID: {cover_item_id})")
                new_book.metadata["OPF"] = {"cover": [("", {"content": cover_item_id})]}

        # Copier le 'spine' (l'ordre de lecture)
        new_book.spine = old_book.spine

        # Copier la 'toc' (Table des matières)
        new_book.toc = old_book.toc

        # 5. Recréer les items de navigation (nécessaire)
        logger.info("Création des fichiers de navigation (NCX/NAV)...")
        new_book.add_item(epub.EpubNcx())
        new_book.add_item(epub.EpubNav())

        # 6. Écriture sécurisée du NOUVEAU livre
        temp_epub_path = epub_path + ".tmp"
        try:
            epub.write_epub(temp_epub_path, new_book)
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

        logger.info("REBUILT EPUB %s with suggested metadata. SUCCESS.", epub_path)
        logger.info("--- FIN UPDATE METADATA (REBUILD) ---")
        return True

    except Exception as e:
        meta.note = f"Error rebuilding epub: {e}\n{traceback.format_exc()}"
        logger.exception("Error rebuilding epub %s", epub_path)
        logger.info("--- FIN UPDATE METADATA AVEC ERREUR ---")
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
