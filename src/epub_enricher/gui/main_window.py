# epub_enricher/src/epub_enricher/gui/main_window.py
"""
Interface utilisateur principale (Orchestrateur/Vue-Contrôleur)
"""

import logging
import tkinter as tk
from io import BytesIO
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Dict, Union

from PIL import Image

from epub_enricher.gui import task_manager

from ..config import GUI_COVER_SIZE, GUI_GEOMETRY, GUI_TITLE
from ..core.models import EpubMeta
from .app_controller import AppController
from .comparison_frame import ComparisonFrame
from .epub_treeview import EpubTreeview  # NOUVEAU
from .main_toolbar import MainToolbar  # NOUVEAU

if TYPE_CHECKING:
    from PIL import ImageTk


logger = logging.getLogger(__name__)


class EnricherGUI(tk.Tk):
    """Orchestrateur graphique principal pour EPUB Enricher."""

    def __init__(self):
        super().__init__()
        self.title(GUI_TITLE)
        self.geometry(GUI_GEOMETRY)

        self.controller = AppController()
        self.cover_photo_cache: Dict[bytes, "ImageTk.PhotoImage"] = {}
        self.current_meta: Union[EpubMeta, None] = None

        # Références aux composants
        self.toolbar: MainToolbar | None = None
        self.tree_frame: EpubTreeview | None = None
        self.comparison_frame: ComparisonFrame | None = None

        self.create_widgets()

        s = ttk.Style()
        self.default_entry_bg = s.lookup("TEntry", "fieldbackground")

    def create_widgets(self):
        """Assemble les composants principaux de l'interface."""
        # --- Top Frame (Toolbar) ---
        self.toolbar = MainToolbar(
            self,
            on_select_folder=self.select_and_scan_folder,
            on_fetch=self.fetch_suggestions_for_selected,
            on_apply=self.apply_changes_to_selected,
        )
        self.toolbar.pack(fill=tk.X, padx=6, pady=6)

        # --- Treeview (Main List) ---
        self.tree_frame = EpubTreeview(self)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree_frame.bind_selection(self.on_tree_select)

        # --- Bottom Frame (Comparison & Actions) ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(bottom)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self.comparison_frame = ComparisonFrame(
            left,
            on_use_original_field=self.choose_field,
            on_use_original_cover=self.choose_cover,
            on_edition_selected_cover=self._start_cover_download_task,
        )
        self.comparison_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Button(right, text="Reset Changes", command=self.reset_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Save CSV", command=self.export_csv).pack(fill=tk.X, padx=4, pady=8)

    # --- Actions (Orchestration) ---
    def select_and_scan_folder(self):
        """Demande un dossier et dit au contrôleur de le charger."""
        folder = filedialog.askdirectory()
        if not folder:
            return
        if self.toolbar:
            self.toolbar.set_folder_var(folder)  # Met à jour la toolbar

        try:
            self.controller.load_from_folder(folder)
            self.refresh_tree()
            self.clear_details()
        except Exception as e:
            logger.exception("Failed to scan folder")
            self.show_error_message("Error", f"An error occurred while scanning: {e}")

    def fetch_suggestions_for_selected(self):
        """Orchestre la recherche de suggestions."""
        if not self.tree_frame:
            return
        indices = self.tree_frame.get_selected_indices()
        if not indices:
            self.show_info_message("Info", "Select one or more files in the list")
            return

        metas_to_fetch = self.controller.get_metas_by_indices(indices)

        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        task_manager.start_fetch_task(metas_to_fetch, on_complete_callback)

    def apply_changes_to_selected(self):
        """Orchestre l'application des modifications."""
        if not self.tree_frame:
            return
        indices = self.tree_frame.get_selected_indices()
        if not indices:
            self.show_info_message("Info", "Select one or more files in the list to apply changes")
            return

        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        to_process = self.controller.get_metas_by_indices(indices)

        if not to_process:
            self.show_info_message("Info", "No valid items selected to apply")
            return

        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        def on_success_callback(msg):
            return self.after(0, lambda: self.show_info_message("Done", msg))

        task_manager.start_apply_task(to_process, on_complete_callback, on_success_callback)

    def reset_selected(self):
        """Demande au contrôleur de réinitialiser les suggestions."""
        if not self.tree_frame:
            return
        indices = self.tree_frame.get_selected_indices()
        if not indices:
            return

        metas_to_reset = self.controller.get_metas_by_indices(indices)
        self.controller.reset_metas(metas_to_reset)
        self.schedule_gui_refresh()

    def export_csv(self):
        """Orchestre l'exportation CSV."""
        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            self.controller.export_to_csv(p)
            self.show_info_message("Success", f"Data exported to {p}")
        except Exception as e:
            self.show_error_message("Error", f"Failed to export CSV: {e}")

    # --- Gestion de l'état de l'interface (Callbacks) ---

    def schedule_gui_refresh(self):
        """Met à jour l'arbre et le panneau de détails."""
        self.refresh_tree()
        self.on_tree_select(None)  # Rafraîchit aussi le panneau de comparaison

    def show_info_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showinfo."""
        messagebox.showinfo(title, message)

    def show_error_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showerror."""
        messagebox.showerror(title, message)

    # --- Gestion de la VUE (Treeview & Details) ---
    def refresh_tree(self):
        """Demande au composant Treeview de se mettre à jour."""
        if self.tree_frame:
            all_meta = self.controller.get_all_meta()
            self.tree_frame.refresh_tree(all_meta)

    def on_tree_select(self, evt=None):
        """Gère la sélection dans le Treeview."""
        if not self.tree_frame:
            return

        new_sel_id = None
        indices = self.tree_frame.get_selected_indices()
        if indices:
            new_sel_id = indices[0]

        new_meta = self.controller.get_meta_by_index(new_sel_id)

        if self.current_meta and self.comparison_frame and (new_meta != self.current_meta):
            try:
                self.comparison_frame.save_final_values_to_model()
            except Exception as e:
                logger.warning("Failed to save previous meta on selection change: %s", e)

        if not new_meta:
            self.clear_details()
            return

        self.current_meta = new_meta
        if self.comparison_frame:
            self.comparison_frame.load_meta(self.current_meta)

    def clear_details(self):
        """Vide le panneau de détails."""
        if self.current_meta and self.comparison_frame:
            try:
                self.comparison_frame.save_final_values_to_model()
            except Exception as e:
                logger.warning("Failed to save previous meta on clear: %s", e)
        if self.comparison_frame:
            self.comparison_frame.load_meta(None)
        self.current_meta = None

    # --- Handlers (appelés par les callbacks de ComparisonFrame) ---

    def choose_field(self, field: str):
        """Handler pour 'on_use_original_field'."""
        if not self.current_meta or not self.comparison_frame:
            return

        if field in ("summary", "tags", "authors"):
            value = getattr(self.current_meta, f"original_{field}", None)
        else:
            value = getattr(self.current_meta, f"original_{field}")
        setattr(self.current_meta, f"suggested_{field}", value)

        try:
            if field == "summary":
                final_text = self.comparison_frame.detail_entries["summary"]["final"]
                final_text.delete(1.0, tk.END)
                final_text.insert(1.0, value or "")
            elif field == "authors" or field == "tags":
                str_value = ", ".join(value or [])
                self.comparison_frame.detail_vars[field]["final"].set(str_value)
            else:
                self.comparison_frame.detail_vars[field]["final"].set(value or "")
            self.comparison_frame.update_comparison_colors()
        except KeyError:
            logger.warning("Tentative de mise à jour d'un champ GUI inconnu : %s", field)
        except Exception as e:
            logger.exception("Erreur lors de la mise à jour directe du champ GUI : %s", e)

    def choose_cover(self):
        """Handler pour 'on_use_original_cover'."""
        if not self.current_meta:
            return
        self.current_meta.suggested_cover_data = self.current_meta.original_cover_data
        self.on_tree_select(None)  # Recharger le panneau

    def _start_cover_download_task(self, meta: "EpubMeta"):
        """
        Handler pour 'on_edition_selected_cover'.
        Démarre une tâche de fond pour télécharger la couverture.
        """

        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        task_manager.start_cover_download_task(meta, on_complete_callback)

    def get_cover_photo(self, data: Union[bytes, None]) -> "ImageTk.PhotoImage | None":
        """Recherche ou crée une image TK pour la couverture (utilisé par ComparisonFrame)."""
        if not data:
            return None
        if data in self.cover_photo_cache:
            return self.cover_photo_cache[data]
        try:
            from PIL import ImageTk
        except ImportError:
            return None
        try:
            pil = Image.open(BytesIO(data))
            pil.thumbnail(GUI_COVER_SIZE)
            tkimg = ImageTk.PhotoImage(pil)
            self.cover_photo_cache[data] = tkimg
            return tkimg
        except Exception:
            logger.exception("Échec de la création de l'aperçu d'image")
            return None
