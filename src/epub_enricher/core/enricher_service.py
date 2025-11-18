# epub_enricher/src/epub_enricher/core/enricher_service.py
"""
Service d'enrichissement EPUB.

Service réutilisable qui orchestre tout le workflow d'enrichissement:
extraction, fetch API, et application des métadonnées.

Ce service est utilisé à la fois par le mode GUI et le mode CLI
pour éviter la duplication de logique.
"""

import logging
import os
from typing import List, Optional

from .epub import extract_metadata, update_epub_with_metadata
from .external_apis import fetch_genre_and_summary_from_sources
from .file_utils import find_epubs_in_folder, rename_epub_file
from .metadata_fetcher import query_openlibrary_full
from .models import EpubMeta

logger = logging.getLogger(__name__)


class EnricherService:
    """
    Service d'enrichissement EPUB.
    
    Fournit les opérations de haut niveau pour enrichir les fichiers EPUB:
    - Extraction de métadonnées depuis les fichiers
    - Récupération de suggestions depuis les APIs externes
    - Application des suggestions aux fichiers
    """
    
    def __init__(self):
        """Initialise le service."""
        logger.debug("EnricherService initialized")
    
    def process_epub(self, epub_path: str) -> Optional[EpubMeta]:
        """
        Traite un fichier EPUB: extrait et enrichit les métadonnées.
        
        Args:
            epub_path: Chemin vers le fichier EPUB
            
        Returns:
            Objet EpubMeta avec métadonnées originales et suggérées,
            ou None en cas d'erreur
        """
        try:
            # 1. Extraction des métadonnées originales
            logger.info(f"Processing EPUB: {epub_path}")
            res = extract_metadata(epub_path)
            
            # 2. Création de l'objet EpubMeta
            meta = EpubMeta(
                path=epub_path,
                filename=os.path.basename(epub_path),
                original_title=res.get("title"),
                original_authors=res.get("authors"),
                original_isbn=res.get("identifier"),
                original_language=res.get("language"),
                original_publisher=res.get("publisher"),
                original_publication_date=res.get("date"),
                original_tags=res.get("tags"),
                original_cover_data=res.get("cover_data"),
                original_summary=res.get("summary"),
            )
            
            # 3. Récupération des suggestions depuis OpenLibrary
            ol_data = query_openlibrary_full(
                title=meta.original_title,
                authors=meta.original_authors,
                isbn=meta.original_isbn,
            )
            
            # 4. Récupération des métadonnées enrichies (genre, résumé, etc.)
            enriched_data = fetch_genre_and_summary_from_sources(
                title=meta.original_title,
                authors=meta.original_authors,
                isbn=meta.original_isbn,
            )
            
            # 5. Remplissage des suggestions
            # Utiliser OpenLibrary comme source principale pour titre/auteurs/langue
            if ol_data.get("related_docs"):
                # Prendre le premier résultat comme meilleure suggestion
                best_doc = ol_data["related_docs"][0]
                meta.suggested_title = best_doc.get("title") or meta.original_title
                
                # Auteurs
                if best_doc.get("author_name"):
                    meta.suggested_authors = best_doc["author_name"]
                else:
                    meta.suggested_authors = meta.original_authors
                    
                # Langue
                if best_doc.get("language"):
                    meta.suggested_language = (
                        best_doc["language"][0] if isinstance(best_doc["language"], list)
                        else best_doc["language"]
                    )
                else:
                    meta.suggested_language = meta.original_language
                    
                # ISBN
                if best_doc.get("isbn"):
                    meta.suggested_isbn = (
                        best_doc["isbn"][0] if isinstance(best_doc["isbn"], list)
                        else best_doc["isbn"]
                    )
                else:
                    meta.suggested_isbn = meta.original_isbn
                    
                # Stocker les éditions alternatives
                meta.found_editions = ol_data.get("related_docs", [])
            else:
                # Fallback: conserver les originaux
                meta.suggested_title = meta.original_title
                meta.suggested_authors = meta.original_authors
                meta.suggested_language = meta.original_language
                meta.suggested_isbn = meta.original_isbn
                meta.found_editions = []
            
            # 6. Appliquer les données enrichies
            meta.suggested_publisher = (
                enriched_data.get("ol_publisher") or meta.original_publisher
            )
            meta.suggested_publication_date = (
                enriched_data.get("ol_pub_date") or meta.original_publication_date
            )
            meta.suggested_tags = (
                enriched_data.get("tags") or meta.original_tags
            )
            meta.suggested_summary = (
                enriched_data.get("summary") or meta.original_summary
            )
            meta.suggested_cover_data = (
                enriched_data.get("cover_data") or meta.original_cover_data
            )
            
            # 7. Marquer comme traité
            meta.processed = True
            meta.note = "Suggestions fetched"
            
            logger.info(f"Successfully processed: {meta.filename}")
            return meta
            
        except Exception as e:
            logger.exception(f"Error processing {epub_path}: {e}")
            return None
    
    def apply_enrichment(self, meta: EpubMeta) -> bool:
        """
        Applique les suggestions de métadonnées à un fichier EPUB.
        
        Args:
            meta: Objet EpubMeta avec suggestions
            
        Returns:
            True si succès, False sinon
        """
        try:
            logger.info(f"Applying enrichment to: {meta.filename}")
            
            # Appliquer les métadonnées
            success = update_epub_with_metadata(meta.path, meta)
            
            if success:
                # Renommer le fichier si nécessaire
                rename_epub_file(meta)
                logger.info(f"Successfully applied enrichment to: {meta.filename}")
                return True
            else:
                logger.error(f"Failed to apply enrichment to: {meta.filename}")
                return False
                
        except Exception as e:
            logger.exception(f"Error applying enrichment to {meta.filename}: {e}")
            meta.note = f"Error: {e}"
            return False
    
    def process_folder(
        self, 
        folder_path: str, 
        autosave: bool = False
    ) -> List[EpubMeta]:
        """
        Traite un dossier entier de fichiers EPUB.
        
        Args:
            folder_path: Chemin vers le dossier
            autosave: Si True, applique automatiquement les suggestions
            
        Returns:
            Liste des objets EpubMeta traités
        """
        logger.info(f"Processing folder: {folder_path}")
        
        # Trouver tous les fichiers EPUB
        files = find_epubs_in_folder(folder_path)
        logger.info(f"Found {len(files)} EPUB files")
        
        metas = []
        for epub_path in files:
            # Traiter chaque fichier
            meta = self.process_epub(epub_path)
            
            if meta:
                metas.append(meta)
                
                # Si autosave, appliquer immédiatement
                if autosave and meta.processed:
                    self.apply_enrichment(meta)
        
        logger.info(f"Processed {len(metas)} files")
        return metas
