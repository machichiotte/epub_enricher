# epub_enricher/src/epub_enricher/gui/main_window.py
"""
Interface utilisateur principale avec Tkinter (Contrôleur/Orchestrateur)
"""

import logging
import os
import tkinter as tk
from io import BytesIO
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Dict, List, Union

from PIL import Image

from ..config import GUI_COVER_SIZE, GUI_GEOMETRY, GUI_TITLE, GUI_TREE_HEIGHT
from ..core.epub_processor import extract_metadata, find_epubs_in_folder
from ..core.models import EpubMeta
from . import helpers, task_manager
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
        self.meta_list: List[EpubMeta] = []
        self.cover_photo_cache: Dict[bytes, "ImageTk.PhotoImage"] = {}
        self.current_meta: Union[EpubMeta, None] = None
        self.comparison_frame: ComparisonFrame | None = None
        self.tree: ttk.Treeview | None = None

        self.create_widgets()

        s = ttk.Style()
        self.default_entry_bg = s.lookup("TEntry", "fieldbackground")

    # (create_widgets reste inchangé)
    def create_widgets(self):
        # --- Top Frame (Buttons) ---
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

        # --- Treeview (Main List) ---
        cols = (
            "filename",
            "title",
            "authors",
            "publisher",
            "isbn",
            "language",
            "date",
            "genre",
            "summary",
            "tags",
            "status",
        )
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=GUI_TREE_HEIGHT)
        column_configs = {
            "filename": {"width": 180, "anchor": "w"},
            "title": {"width": 200, "anchor": "w"},
            "authors": {"width": 150, "anchor": "w"},
            "publisher": {"width": 100, "anchor": "w"},
            "isbn": {"width": 90, "anchor": "w"},
            "language": {"width": 70, "anchor": "w"},
            "date": {"width": 70, "anchor": "w"},
            "genre": {"width": 100, "anchor": "w"},
            "summary": {"width": 150, "anchor": "w"},
            "tags": {"width": 100, "anchor": "w"},
            "status": {"width": 90, "anchor": "w"},
        }
        for c in cols:
            # Lier l'en-tête de colonne à la méthode de tri
            self.tree.heading(
                c,
                text=c.replace("_", " ").capitalize(),
                command=lambda col=c: self.sort_treeview_column(self.tree, col, False),
            )
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.tree.column(c, width=config["width"], anchor=config["anchor"])

        self.tree.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- Bottom Frame (Details & Actions) ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(bottom)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        self.comparison_frame = ComparisonFrame(left, self)
        self.comparison_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Button(right, text="Reset Changes", command=self.reset_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Save CSV", command=self.export_csv).pack(fill=tk.X, padx=4, pady=8)

    # --- Actions (Orchestration) ---
    def select_and_scan_folder(self):
        """Combine la sélection et le scan du dossier en une seule action."""
        folder = filedialog.askdirectory()
        if not folder:
            return  # Annulé par l'utilisateur
        self.folder_var.set(folder)

        if not os.path.isdir(folder):
            self.show_error_message("Error", "Select a valid folder first")
            return

        try:
            self.scan_folder()
        except Exception as e:
            logger.exception("Failed to scan folder")
            self.show_error_message("Error", f"An error occurred while scanning: {e}")

    def scan_folder(self):
        folder = self.folder_var.get()
        if not folder or not os.path.isdir(folder):
            self.show_error_message("Error", "Select a valid folder first")
            return

        files = find_epubs_in_folder(folder)
        self.meta_list = []
        for p in files:
            res = extract_metadata(p)

            # 1. Créer l'objet meta SANS le nouvel argument
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
                content_isbn=res.get("content_isbn"),
                content_summary=res.get("content_summary"),
                content_genre=res.get("content_genre"),
                content_publisher=res.get("content_publisher"),
                content_publication_date=res.get("content_publication_date"),
                content_edition_info=res.get("content_edition_info"),
                content_analysis=res.get("content_analysis"),
                # Ne pas mettre 'found_editions' ici
            )

            # 2. ASSIGNER le nouvel attribut APRES la création
            meta_obj.found_editions = []

            # 3. Ajouter l'objet complété à la liste
            self.meta_list.append(meta_obj)

        self.refresh_tree()
        self.clear_details()

    def fetch_suggestions_for_selected(self):
        """Délègue la recherche de suggestions au TaskManager."""
        sel = self.tree.selection()
        if not sel:
            self.show_info_message("Info", "Select one or more files in the list")
            return
        # Délégation !
        task_manager.start_fetch_task(self, sel)

    def apply_accepted(self):
        """Délègue l'application des modifications au TaskManager."""

        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        to_process = [m for m in self.meta_list if m.accepted]
        if not to_process:
            self.show_info_message("Info", "No accepted items to apply")
            return
        # Délégation !
        task_manager.start_apply_task(self, to_process)

    def apply_changes_to_selected(self):
        """
        Délègue l'application des modifications au TaskManager pour les
        fichiers actuellement sélectionnés dans l'arbre.
        """
        sel = self.tree.selection()
        if not sel:
            self.show_info_message("Info", "Select one or more files in the list to apply changes")
            return

        # Sauvegarder les modifications en cours sur l'item actuellement
        # affiché dans le comparison_frame, au cas où il serait
        # dans la sélection mais pas encore sauvegardé.
        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        # Construire la liste des objets meta à traiter
        to_process = [self.meta_list[int(s)] for s in sel]

        if not to_process:
            # Ne devrait pas arriver si 'sel' n'est pas vide, mais par sécurité
            self.show_info_message("Info", "No valid items selected to apply")
            return

        # Délégation !
        task_manager.start_apply_task(self, to_process)

    def reset_selected(self):
        """Réinitialise les champs 'Valeur à appliquer' (suggested_)."""
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            # Utilisation de l'helper pour réinitialiser le modèle
            helpers.reset_suggestions_on_model(self.meta_list[int(s)])

        # Rafraîchir l'interface pour montrer la réinitialisation
        self.schedule_gui_refresh()

    def export_csv(self):
        """Délègue l'exportation CSV à l'helper."""

        # Sauvegarder les modifications en cours sur l'item
        if self.current_meta and self.comparison_frame:
            self.comparison_frame.save_final_values_to_model()

        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            # Délégation !
            helpers.export_to_csv(p, self.meta_list)
            self.show_info_message("Success", f"Data exported to {p}")
        except Exception as e:
            self.show_error_message("Error", f"Failed to export CSV: {e}")

    # --- Gestion de l'état de l'interface (Callbacks depuis les workers) ---

    def schedule_gui_refresh(self):
        """Met à jour l'arbre et le panneau de détails (appelé depuis un thread)."""
        self.refresh_tree()
        self.on_select(None)  # Rafraîchit aussi le panneau de comparaison

    def show_info_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showinfo."""
        messagebox.showinfo(title, message)

    def show_error_message(self, title: str, message: str):
        """Wrapper thread-safe pour messagebox.showerror."""
        messagebox.showerror(title, message)

    # --- Gestion de la VUE (Treeview & Details) ---
    def refresh_tree(self):
        selected_ids = self.tree.selection()
        self.tree.delete(*self.tree.get_children())

        for idx, m in enumerate(self.meta_list):
            # Utilisation de l'helper
            quality_score = helpers.calculate_metadata_quality(m)
            vals = self._get_tree_values_for_meta(m, quality_score)
            self.tree.insert("", "end", iid=str(idx), values=vals)

        if selected_ids:
            try:
                self.tree.selection_set(selected_ids)
            except tk.TclError:
                pass

    def sort_treeview_column(self, tree, col, reverse):
        """Trie les données du Treeview par la colonne spécifiée."""
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
        """Helper interne pour formater les valeurs du Treeview."""
        status_text = "processed" if m.processed else "idle"
        if quality_score > 0:
            status_text += f" ({quality_score}%)"
        summary_text = m.suggested_summary or m.content_summary or ""
        summary_preview = (summary_text[:50] + "...") if len(summary_text) > 50 else summary_text
        return (
            m.filename,
            m.suggested_title or m.original_title or "",
            ", ".join(m.suggested_authors or m.original_authors or []),
            m.suggested_publisher or m.original_publisher or "",
            m.suggested_isbn or m.original_isbn or "",
            m.suggested_language or m.original_language or "",
            m.suggested_publication_date or m.original_publication_date or "",
            m.suggested_genre or m.content_genre or "",
            summary_preview,
            ", ".join(m.suggested_tags or m.original_tags or []),
            status_text,
        )

    def on_select(self, evt=None):
        # Trouver le NOUVEL item sélectionné
        new_sel_id = None
        sel = self.tree.selection()
        if sel:
            new_sel_id = int(sel[0])

        # Si l'objet méta actuel est différent du nouveau, SAUVEGARDER l'ancien.
        if (
            self.current_meta
            and self.comparison_frame
            and (new_sel_id is None or self.meta_list[new_sel_id] != self.current_meta)
        ):
            try:
                self.comparison_frame.save_final_values_to_model()
            except Exception as e:
                logger.warning("Failed to save previous meta on selection change: %s", e)

        if not sel:
            self.clear_details()
            return

        self.current_meta = self.meta_list[new_sel_id]
        if self.comparison_frame:
            self.comparison_frame.load_meta(self.current_meta)

    def clear_details(self):
        if self.current_meta and self.comparison_frame:
            try:
                self.comparison_frame.save_final_values_to_model()
            except Exception as e:
                logger.warning("Failed to save previous meta on clear: %s", e)

        if self.comparison_frame:
            self.comparison_frame.load_meta(None)
        self.current_meta = None

    # --- Callbacks (appelés depuis ComparisonFrame & EditionsWindow) ---

    def choose_field(self, field: str, side: str):
        if not self.current_meta or side != "orig":
            return

        value = (
            getattr(self.current_meta, f"content_{field}", None)
            if field in ("summary", "genre")
            else getattr(self.current_meta, f"original_{field}")
        )

        setattr(self.current_meta, f"suggested_{field}", value)

        if self.comparison_frame:
            self.comparison_frame.load_meta(self.current_meta)

    def choose_cover(self, side: str):
        if not self.current_meta or side != "orig":
            return
        self.current_meta.suggested_cover_data = self.current_meta.original_cover_data
        self.on_select(None)  # Recharger le panneau

    # (get_cover_photo reste inchangé)
    def get_cover_photo(self, data: Union[bytes, None]) -> "ImageTk.PhotoImage | None":
        """Charge une image depuis les données binaires et la met en cache."""
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

    # --- MÉTHODES OBSOLÈTES ---
    # def launch_editions_window(self, docs: List[Dict]):
    #     """(OBSOLÈTE) Ouvre la fenêtre modale des éditions."""
    #     if not docs:
    #         return
    #     EditionsWindow(self, docs, self._on_edition_selected)
    #
    # def _on_edition_selected(self, selected_doc: Dict):
    #     """(OBSOLÈTE) Applique les métadonnées de l'édition sélectionnée."""
    #     pass # La logique est maintenant dans ComparisonFrame

    def _update_cover_for_edition(self, meta: "EpubMeta"):
        """
        Petit worker pour juste re-télécharger la couverture.
        (Appelé par ComparisonFrame)
        """
        task_manager._download_cover_data(meta)
        self.after(0, self.schedule_gui_refresh)
