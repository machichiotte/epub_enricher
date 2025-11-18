# epub_enricher/src/epub_enricher/gui/app_controller.py
"""
Contrôleur de données (Gestionnaire d'état).

Ce module centralise la logique de gestion de la liste des métadonnées (EpubMeta),
la chargeant depuis le disque et la manipulant, indépendamment de l'interface
graphique.
"""

import logging
import os
from typing import List

from ..core.epub import extract_metadata
from ..core.file_utils import find_epubs_in_folder
from ..core.models import EpubMeta
from . import helpers

logger = logging.getLogger(__name__)


class AppController:
    """Gère l'état de la liste des métadonnées de l'application."""

    def __init__(self):
        self.meta_list: List[EpubMeta] = []
        logger.debug("AppController initialisé.")

    def load_from_folder(self, folder_path: str):
        """
        Scanne un dossier, extrait les métadonnées et remplit self.meta_list.
        """
        if not folder_path or not os.path.isdir(folder_path):
            raise ValueError("Le chemin du dossier est invalide.")

        logger.info(f"Scan du dossier : {folder_path}")
        files = find_epubs_in_folder(folder_path)

        new_meta_list = []
        for p in files:
            meta_obj = self._create_meta_from_file(p)
            if meta_obj:
                new_meta_list.append(meta_obj)

        self.meta_list = new_meta_list
        logger.info(f"{len(self.meta_list)} EPUBs chargés.")

    def _create_meta_from_file(self, p: str) -> EpubMeta | None:
        """Tente d'extraire les métadonnées et de créer un objet EpubMeta."""
        try:
            res = extract_metadata(p)
            meta_obj = EpubMeta(
                path=p,
                filename=os.path.basename(p),
                original_title=res.get("title"),
                original_authors=res.get("authors"),
                original_isbn=res.get("identifier"),
                original_language=res.get("language"),
                original_tags=res.get("tags"),
                original_publisher=res.get("publisher"),
                original_publication_date=res.get("date"),
                original_cover_data=res.get("cover_data"),
                original_summary=res.get("summary"),
            )
            # Attribut requis par la GUI
            meta_obj.found_editions = []
            return meta_obj
        except Exception as e:
            logger.error(f"Échec de l'extraction des métadonnées pour {p}: {e}")
            return None

    def get_all_meta(self) -> List[EpubMeta]:
        """Retourne la liste complète des métadonnées."""
        return self.meta_list

    def get_meta_by_index(self, index: int) -> EpubMeta | None:
        """Retourne un objet meta par son index dans la liste."""
        if 0 <= index < len(self.meta_list):
            return self.meta_list[index]
        return None

    def get_metas_by_indices(self, indices: List[int]) -> List[EpubMeta]:
        """Retourne une liste d'objets meta basée sur une liste d'indices."""
        metas = []
        for idx in indices:
            meta = self.get_meta_by_index(idx)
            if meta:
                metas.append(meta)
        return metas

    def reset_metas(self, metas_to_reset: List[EpubMeta]):
        """Réinitialise les champs 'suggested' pour les objets meta fournis."""
        logger.info(f"Réinitialisation de {len(metas_to_reset)} objets meta.")
        for m in metas_to_reset:
            # Utilisation de l'helper pour réinitialiser le modèle
            helpers.reset_suggestions_on_model(m)

    def export_to_csv(self, filepath: str):
        """
        Exporte l'état actuel de self.meta_list vers un fichier CSV.
        """
        if not filepath:
            raise ValueError("Chemin de fichier non valide pour l'export CSV.")

        logger.info(f"Export CSV vers {filepath}")
        try:
            # Délégation à l'helper
            helpers.export_to_csv(filepath, self.meta_list)
        except Exception:
            logger.exception(f"Échec de l'export CSV vers {filepath}")
            # Fait remonter l'exception pour que la GUI puisse l'afficher
            raise
