# epub_enricher/src/epub_enricher/gui/editions_window.py
"""
Fenêtre Toplevel pour afficher et sélectionner
parmi les éditions alternatives trouvées sur OpenLibrary.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, List


class EditionsWindow(tk.Toplevel):
    """
    Une fenêtre Toplevel qui affiche une liste d'éditions
    et renvoie la sélection via un callback.
    """

    def __init__(self, master, docs: List[Dict], select_callback: Callable):
        super().__init__(master)
        self.title("Éditions disponibles")
        self.geometry("1200x400")

        self.docs = docs
        self.select_callback = select_callback
        self.tree: ttk.Treeview | None = None

        self._create_widgets()
        self._populate_tree()

        # Rendre la fenêtre modale
        self.transient(master)
        self.grab_set()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info_label = ttk.Label(
            main_frame,
            text=f"Trouvé {len(self.docs)} édition(s) sur OpenLibrary",
            font=("TkDefaultFont", 10, "bold"),
        )
        info_label.pack(pady=(0, 10))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("title", "authors", "language", "isbn", "publisher", "year", "quality")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")

        column_configs = {
            "title": {"width": 250, "anchor": "w"},
            "authors": {"width": 200, "anchor": "w"},
            "language": {"width": 80, "anchor": "w"},
            "isbn": {"width": 120, "anchor": "w"},
            "publisher": {"width": 150, "anchor": "w"},
            "year": {"width": 80, "anchor": "w"},
            "quality": {"width": 80, "anchor": "w"},
        }

        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.tree.column(c, width=config["width"], anchor=config["anchor"])

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Fermer", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(
            button_frame,
            text="Sélectionner cette édition",
            command=self._on_select,
        ).pack(side=tk.LEFT)

    def _populate_tree(self):
        for i, doc in enumerate(self.docs):
            details = doc.get("edition_details") or doc.get("work_details") or doc
            title = details.get("title", doc.get("title", ""))

            authors_list = (
                details.get("author_name")
                or (
                    [a["name"] for a in details["authors"]]
                    if isinstance(details.get("authors"), list)
                    and details["authors"]
                    and isinstance(details["authors"][0], dict)
                    and "name" in details["authors"][0]
                    else []
                )
                or doc.get("author_name")
            )
            authors = ", ".join(authors_list or [])

            langs_obj = details.get("languages", doc.get("language", []))
            if (
                isinstance(langs_obj, list)
                and langs_obj
                and isinstance(langs_obj[0], dict)
                and "key" in langs_obj[0]
            ):
                lang = ", ".join(
                    [
                        lang_item.get("key", "").split("/")[-1]
                        for lang_item in langs_obj
                        if lang_item.get("key")
                    ]
                )
            else:
                lang = ", ".join(langs_obj or [])

            isbn_list = details.get("isbn_13", []) + details.get("isbn_10", [])
            isbns = ", ".join(isbn_list[:2] or doc.get("isbn", [])[:2])

            pubs_obj = details.get("publishers", doc.get("publisher", []))
            if (
                isinstance(pubs_obj, list)
                and pubs_obj
                and isinstance(pubs_obj[0], dict)
                and "name" in pubs_obj[0]
            ):
                publisher = ", ".join([p.get("name") for p in pubs_obj if p.get("name")])
            else:
                publisher = ", ".join(pubs_obj or [])

            year = (
                details.get("publish_date")
                or str(details.get("first_publish_year", ""))
                or str(doc.get("first_publish_year", ""))
            )

            quality_score = 0
            if title:
                quality_score += 20
            if authors:
                quality_score += 20
            if isbns:
                quality_score += 20
            if publisher:
                quality_score += 20
            if year:
                quality_score += 20
            quality_text = f"{quality_score}%"

            # Utiliser l'index 'i' comme IID pour retrouver le 'doc'
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(title, authors, lang, isbns, publisher, year, quality_text),
            )

    def _on_select(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une édition", parent=self)
            return

        # Récupérer l'IID, qui est l'index dans self.docs
        selected_index = int(selection[0])
        selected_doc = self.docs[selected_index]

        if not selected_doc:
            messagebox.showerror("Erreur", "Édition non trouvée", parent=self)
            return

        # Appeler le callback avec le document sélectionné
        self.select_callback(selected_doc)
        self.destroy()
