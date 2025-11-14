# epub_enricher/src/epub_enricher/gui/epub_treeview.py
"""
Composant GUI pour le Treeview principal affichant les EPUBs.
"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, List

from ..config import GUI_TREE_HEIGHT
from ..core.models import EpubMeta
from . import helpers

if TYPE_CHECKING:
    from ..core.models import EpubMeta


class EpubTreeview(ttk.Frame):
    """Frame contenant le Treeview principal et sa logique."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.tree: ttk.Treeview | None = None
        self._create_widgets()

    def _create_widgets(self):
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

        column_configs = {
            "filename": {"width": 180, "anchor": "w"},
            "title": {"width": 200, "anchor": "w"},
            # ... (autres configs de colonnes) ...
        }

        for c in cols:
            self.tree.heading(
                c,
                text=c.replace("_", " ").capitalize(),
                command=lambda col=c: self.sort_treeview_column(col, False),
            )
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.tree.column(c, width=config["width"], anchor=config["anchor"])

        # Ajout de scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def bind_selection(self, callback: Callable):
        """Permet au parent de s'abonner à l'événement de sélection."""
        self.tree.bind("<<TreeviewSelect>>", callback)

    def get_selected_indices(self) -> List[int]:
        """Retourne les index (iid) des items sélectionnés."""
        return [int(s) for s in self.tree.selection()]

    def refresh_tree(self, all_meta: List[EpubMeta]):
        """Met à jour le Treeview avec la liste complète des métadonnées."""
        selected_ids = self.tree.selection()
        self.tree.delete(*self.tree.get_children())

        for idx, m in enumerate(all_meta):
            quality_score = helpers.calculate_metadata_quality(m)
            vals = self._get_tree_values_for_meta(m, quality_score)
            self.tree.insert("", "end", iid=str(idx), values=vals)

        if selected_ids:
            try:
                self.tree.selection_set(selected_ids)
            except tk.TclError:
                pass

    def _get_tree_values_for_meta(self, m: EpubMeta, quality_score: int) -> tuple:
        """Helper pour formater une ligne du Treeview."""
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
            # ... (autres champs) ...
            summary_preview,
            status_text,
        )

    def sort_treeview_column(self, col, reverse):
        """Trie les données du Treeview."""
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children("")]

        # ... (logique de conversion et de tri identique à l'original) ...
        # (Cette fonction est complexe mais fait une seule chose : trier)

        for index, (val, child) in enumerate(data):
            self.tree.move(child, "", index)
        self.tree.heading(
            col,
            command=lambda c=col: self.sort_treeview_column(c, not reverse),
        )
