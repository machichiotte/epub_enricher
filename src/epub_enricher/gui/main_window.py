# epub_enricher/src/epub_enricher/gui/main_window.py
"""
Interface utilisateur principale avec Tkinter (Orchestrateur/Vue-Contrôleur)
"""

import logging
import tkinter as tk
from io import BytesIO
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Dict, Union

from PIL import Image

from ..config import GUI_COVER_SIZE, GUI_GEOMETRY, GUI_TITLE, GUI_TREE_HEIGHT

# Les importations core (extract, find) ne sont plus nécessaires ici
from ..core.models import EpubMeta
from . import helpers, task_manager
from .app_controller import AppController  # Importer le nouveau contrôleur
from .comparison_frame import ComparisonFrame

if TYPE_CHECKING:
    from PIL import ImageTk


logger = logging.getLogger(__name__)


class EnricherGUI(tk.Tk):
    """Interface graphique principale pour EPUB Enricher."""

    def __init__(self):
        super().__init__()
        self.title(GUI_TITLE)
        self.geometry(GUI_GEOMETRY)

        # Le contrôleur gère l'état (la liste)
        self.controller = AppController()

        # self.meta_list n'existe plus ici
        self.cover_photo_cache: Dict[bytes, "ImageTk.PhotoImage"] = {}
        self.current_meta: Union[EpubMeta, None] = None
        self.comparison_frame: ComparisonFrame | None = None
        self.tree: ttk.Treeview | None = None

        self.create_widgets()

        s = ttk.Style()
        self.default_entry_bg = s.lookup("TEntry", "fieldbackground")

    def create_widgets(self):
        # --- Top Frame (Buttons) (Identique) ---
        frm_top = ttk.Frame(self)
        frm_top.pack(fill=tk.X, padx=6, pady=6)
        self.folder_var = tk.StringVar()
        ttk.Entry(frm_top, textvariable=self.folder_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Select & Scan Folder", command=self.select_and_scan_folder).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(
            frm_top, text="Fetch suggestions", command=self.fetch_suggestions_for_selected
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Apply Changes", command=self.apply_changes_to_selected).pack(
            side=tk.LEFT, padx=4
        )

        # --- Treeview (Main List) (Identique) ---
        cols = (
            "filename",
            "title",
            "authors",
            "publisher",
            "isbn",
            "language",
            "date",
            "tags",
            "summary",
            "status",
        )
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=GUI_TREE_HEIGHT)
        # ... (Configuration du Treeview identique) ...
        column_configs = {
            "filename": {"width": 180, "anchor": "w"},
            "title": {"width": 200, "anchor": "w"},
            "authors": {"width": 150, "anchor": "w"},
            "publisher": {"width": 100, "anchor": "w"},
            "isbn": {"width": 90, "anchor": "w"},
            "language": {"width": 70, "anchor": "w"},
            "date": {"width": 70, "anchor": "w"},
            "summary": {"width": 150, "anchor": "w"},
            "tags": {"width": 100, "anchor": "w"},
            "status": {"width": 90, "anchor": "w"},
        }
        for c in cols:
            self.tree.heading(
                c,
                text=c.replace("_", " ").capitalize(),
                command=lambda col=c: self.sort_treeview_column(self.tree, col, False),
            )
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.tree.column(c, width=config["width"], anchor=config["anchor"])
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- Bottom Frame (Modification : injection des callbacks) ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(bottom)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        # *** MODIFICATION ICI ***
        # Injecter les méthodes de cette classe (les handlers)
        # dans le ComparisonFrame.
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

    # --- Actions (Orchestration - Modifiées) ---
    def select_and_scan_folder(self):
        """Demande un dossier et dit au contrôleur de le charger."""
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.folder_var.set(folder)

        try:
            # Délégué au contrôleur
            self.controller.load_from_folder(folder)
            self.refresh_tree()
            self.clear_details()
        except Exception as e:
            logger.exception("Failed to scan folder")
            self.show_error_message("Error", f"An error occurred while scanning: {e}")

    # scan_folder() est supprimé (logique déplacée vers AppController)

    def fetch_suggestions_for_selected(self):
        """Orchestre la recherche de suggestions."""
        sel = self.tree.selection()
        if not sel:
            self.show_info_message("Info", "Select one or more files in the list")
            return

        # 1. Obtenir les objets Meta depuis le contrôleur
        indices = [int(s) for s in sel]
        metas_to_fetch = self.controller.get_metas_by_indices(indices)

        # 2. Définir le callback (ce qu'il faut faire une fois terminé)
        #    Nous utilisons self.after pour garantir l'exécution dans le thread GUI
        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        # 3. Démarrer la tâche de fond
        task_manager.start_fetch_task(metas_to_fetch, on_complete_callback)

    # apply_accepted() est supprimé (redondant avec apply_changes_to_selected)

    def apply_changes_to_selected(self):
        """Orchestre l'application des modifications."""
        sel = self.tree.selection()
        if not sel:
            self.show_info_message("Info", "Select one or more files in the list to apply changes")
            return

        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        # 1. Obtenir les objets Meta depuis le contrôleur
        indices = [int(s) for s in sel]
        to_process = self.controller.get_metas_by_indices(indices)

        if not to_process:
            self.show_info_message("Info", "No valid items selected to apply")
            return

        # 2. Définir les callbacks
        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        def on_success_callback(msg):
            return self.after(0, lambda: self.show_info_message("Done", msg))

        # 3. Démarrer la tâche de fond
        task_manager.start_apply_task(to_process, on_complete_callback, on_success_callback)

    def reset_selected(self):
        """Demande au contrôleur de réinitialiser les suggestions."""
        sel = self.tree.selection()
        if not sel:
            return

        # 1. Obtenir les objets Meta
        indices = [int(s) for s in sel]
        metas_to_reset = self.controller.get_metas_by_indices(indices)

        # 2. Demander la réinitialisation au contrôleur
        self.controller.reset_metas(metas_to_reset)

        # 3. Rafraîchir l'interface
        self.schedule_gui_refresh()

    def export_csv(self):
        """Orchestre l'exportation CSV."""
        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            # Délégué au contrôleur
            self.controller.export_to_csv(p)
            self.show_info_message("Success", f"Data exported to {p}")
        except Exception as e:
            self.show_error_message("Error", f"Failed to export CSV: {e}")

    # --- Gestion de l'état de l'interface (Callbacks) ---

    def schedule_gui_refresh(self):
        """Met à jour l'arbre et le panneau de détails."""
        self.refresh_tree()
        self.on_select(None)  # Rafraîchit aussi le panneau de comparaison

    def show_info_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showinfo."""
        messagebox.showinfo(title, message)

    def show_error_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showerror."""
        messagebox.showerror(title, message)

    # --- Gestion de la VUE (Treeview & Details - Modifiée) ---
    def refresh_tree(self):
        """Met à jour le Treeview en lisant depuis le contrôleur."""
        selected_ids = self.tree.selection()
        self.tree.delete(*self.tree.get_children())

        # Obtenir les données depuis le contrôleur
        all_meta = self.controller.get_all_meta()

        for idx, m in enumerate(all_meta):
            quality_score = helpers.calculate_metadata_quality(m)
            vals = self._get_tree_values_for_meta(m, quality_score)
            self.tree.insert("", "end", iid=str(idx), values=vals)

        if selected_ids:
            try:
                self.tree.selection_set(selected_ids)
            except tk.TclError:
                pass

    def sort_treeview_column(self, tree, col, reverse):
        """Trie les données du Treeview (Identique)."""
        # ... (Aucun changement) ...
        data = [(tree.set(child, col), child) for child in tree.get_children("")]

        def convert_key(item):
            value = item[0]
            if col == "status" and "(" in value:
                try:
                    return int(value.split("(")[1].split("%")[0])
                except (ValueError, IndexError):
                    return value
            try:
                return float(value)
            except ValueError:
                return value.lower()

        data.sort(key=convert_key, reverse=reverse)
        for index, (val, child) in enumerate(data):
            tree.move(child, "", index)
        tree.heading(
            col,
            command=lambda c=col: self.sort_treeview_column(tree, c, not reverse),
        )

    def _get_tree_values_for_meta(self, m: EpubMeta, quality_score: int) -> tuple:
        """Helper interne (Identique)."""
        # ... (Aucun changement) ...
        status_text = "processed" if m.processed else "idle"
        if quality_score > 0:
            status_text += f" ({quality_score}%)"
        summary_text = m.suggested_summary or m.original_summary or ""
        summary_preview = (summary_text[:50] + "...") if len(summary_text) > 50 else summary_text
        return (
            m.filename,
            m.suggested_title or m.original_title or "",
            ", ".join(m.suggested_authors or m.original_authors or []),
            m.suggested_publisher or m.original_publisher or "",
            m.suggested_isbn or m.original_isbn or "",
            m.suggested_language or m.original_language or "",
            m.suggested_publication_date or m.original_publication_date or "",
            ", ".join(m.suggested_tags or m.original_tags or []),
            summary_preview,
            status_text,
        )

    def on_select(self, evt=None):
        """Gère la sélection dans le Treeview (Modifié)."""
        new_sel_id = None
        sel = self.tree.selection()
        if sel:
            new_sel_id = int(sel[0])

        # Obtenir le nouvel objet meta depuis le contrôleur
        new_meta = self.controller.get_meta_by_index(new_sel_id) if new_sel_id is not None else None

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
        """Vide le panneau de détails (Identique)."""
        # ... (Aucun changement) ...
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
        """Handler pour 'on_use_original_field' (Logique identique)."""
        if not self.current_meta or not self.comparison_frame:
            return

        # ... (Logique identique à l'ancienne méthode) ...
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
        """Handler pour 'on_use_original_cover' (Logique identique)."""
        if not self.current_meta:
            return
        self.current_meta.suggested_cover_data = self.current_meta.original_cover_data
        self.on_select(None)  # Recharger le panneau

    def _start_cover_download_task(self, meta: "EpubMeta"):
        """
        Handler pour 'on_edition_selected_cover'.
        Démarre une tâche de fond pour télécharger la couverture.
        """

        def on_complete_callback():
            return self.after(0, self.schedule_gui_refresh)

        task_manager.start_cover_download_task(meta, on_complete_callback)

    # --- (get_cover_photo reste inchangé) ---
    def get_cover_photo(self, data: Union[bytes, None]) -> "ImageTk.PhotoImage | None":
        # ... (Aucun changement) ...
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

    # _update_cover_for_edition est renommé _start_cover_download_task
