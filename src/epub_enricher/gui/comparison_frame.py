# epub_enricher/src/epub_enricher/gui/comparison_frame.py
"""
Composant GUI pour la zone de comparaison et de sélection des métadonnées.
"""

import logging
import tkinter as tk
from io import BytesIO
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, Dict, List, Union

from PIL import Image, ImageTk

from ..config import GUI_COVER_SIZE

if TYPE_CHECKING:
    from ..core.models import EpubMeta

logger = logging.getLogger(__name__)


class ComparisonFrame(ttk.LabelFrame):
    """
    Frame contenant les vues "Original", "Final", les couvertures
    ET la liste des éditions pour la comparaison des métadonnées.
    """

    def __init__(
        self,
        master,
        on_use_original_field: Callable[[str], None],
        on_use_original_cover: Callable[[], None],
        on_edition_selected_cover: Callable[["EpubMeta"], None],
        **kwargs,
    ):
        super().__init__(master, text="Comparaison et Sélection", **kwargs)

        # Stocker les callbacks
        self.on_use_original_field = on_use_original_field
        self.on_use_original_cover = on_use_original_cover
        self.on_edition_selected_cover = on_edition_selected_cover

        self.current_meta: Union["EpubMeta", None] = None
        self.editions_tree: Union[ttk.Treeview, None] = None

        self.detail_vars: Dict[str, Dict[str, tk.StringVar]] = {}
        self.detail_entries: Dict[str, Dict[str, ttk.Entry | tk.Text]] = {}

        self.create_comparison_widgets()

    def create_comparison_widgets(self):
        """Crée et dispose les widgets de comparaison."""
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=2)
        self.columnconfigure(3, weight=1)
        self.columnconfigure(4, weight=2)

        self._create_headers()
        self._create_cover_widgets()
        self._create_metadata_fields()
        self._create_editions_tree()

    def _create_headers(self):
        """Crée les en-têtes de colonnes."""
        ttk.Label(self, text="Couverture originale", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, padx=6, pady=3, sticky="w"
        )
        ttk.Label(self, text="Couverture suggérée", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=5, padx=6, pady=3, sticky="w"
        )
        ttk.Label(self, text="Champ", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=1, padx=5, pady=3, sticky="w"
        )
        ttk.Label(self, text="Original", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=2, padx=5, pady=3, sticky="w"
        )
        ttk.Label(self, text="Valeur à appliquer", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=4, padx=5, pady=3, sticky="w"
        )

    def _create_cover_widgets(self):
        """Crée les canvas pour les couvertures."""
        self.cover_orig_canvas = tk.Canvas(
            self,
            width=GUI_COVER_SIZE[0],
            height=GUI_COVER_SIZE[1],
            bg="#EEE",
            highlightthickness=2,
            highlightbackground="#880000",
            relief="raised",
            bd=2,
        )
        self.cover_orig_canvas.grid(row=1, column=0, rowspan=20, padx=6, pady=6, sticky="n")

        self.cover_final_canvas = tk.Canvas(
            self,
            width=GUI_COVER_SIZE[0],
            height=GUI_COVER_SIZE[1],
            bg="#EEE",
            highlightthickness=2,
            highlightbackground="#004488",
            relief="raised",
            bd=2,
        )
        self.cover_final_canvas.grid(row=1, column=5, rowspan=20, padx=6, pady=6, sticky="n")

    def _create_metadata_fields(self):
        """Crée les champs de métadonnées (titre, auteurs, etc.)."""
        fields = [
            "title",
            "authors",
            "publisher",
            "isbn",
            "language",
            "publication_date",
            "tags",
        ]
        row_idx = 0
        for i, field in enumerate(fields, start=1):
            row_idx = i
            self._create_field_row(field, row_idx)

        # Champ Résumé (summary) géré séparément
        row_idx += 1
        self._create_summary_row(row_idx)

        # Bouton "Utiliser cette couverture"
        ttk.Button(
            self,
            text="Utiliser cette couverture →",
            command=self.on_use_original_cover,  # Appelle le callback
        ).grid(row=row_idx + 1, column=0, columnspan=2, pady=(10, 6))

    def _create_field_row(self, field: str, row: int):
        """Crée une ligne de widgets pour un champ spécifique."""
        ttk.Label(self, text=field.replace("_", " ").capitalize()).grid(
            row=row, column=1, padx=5, pady=5, sticky="w"
        )
        self.detail_vars[field] = {"orig": tk.StringVar(), "final": tk.StringVar()}

        orig_entry = ttk.Entry(self, textvariable=self.detail_vars[field]["orig"], state="readonly")
        orig_entry.grid(row=row, column=2, sticky="ew", padx=5)

        final_entry = ttk.Entry(self, textvariable=self.detail_vars[field]["final"])
        final_entry.grid(row=row, column=4, sticky="ew", padx=5)

        self.detail_entries[field] = {"orig": orig_entry, "final": final_entry}

        use_btn = ttk.Button(
            self,
            text="→",
            width=4,
            command=lambda f=field: self.on_use_original_field(f),
        )
        use_btn.grid(row=row, column=3, padx=2, pady=2)

    def _create_summary_row(self, row: int):
        """Crée la ligne de widgets pour le champ résumé (Text)."""
        field = "summary"
        ttk.Label(self, text="Summary").grid(row=row, column=1, padx=5, pady=5, sticky="w")
        # Pas de StringVar pour les widgets Text
        self.detail_vars[field] = {"orig": None, "final": None}

        orig_text = tk.Text(self, height=3, width=30, state="disabled", wrap=tk.WORD)
        orig_text.grid(row=row, column=2, sticky="ew", padx=5)

        final_text = tk.Text(self, height=3, width=30, wrap=tk.WORD)
        final_text.grid(row=row, column=4, sticky="ew", padx=5)

        self.detail_entries[field] = {"orig": orig_text, "final": final_text}

        use_btn = ttk.Button(
            self,
            text="→",
            width=4,
            command=lambda f=field: self.on_use_original_field(f),
        )
        use_btn.grid(row=row, column=3, padx=2, pady=2)

    def _create_editions_tree(self):
        """Crée le treeview pour les éditions trouvées."""
        editions_frame = ttk.LabelFrame(self, text="Éditions trouvées (OpenLibrary)")
        # Place le cadre après les champs de métadonnées
        editions_frame.grid(
            row=20,  # Row 20 (assez bas pour être en dessous des champs)
            column=1,
            columnspan=4,
            sticky="ew",
            padx=5,
            pady=(10, 5),
        )
        editions_frame.columnconfigure(0, weight=1)

        cols = ("title", "authors", "isbn", "year", "lang", "quality")
        self.editions_tree = ttk.Treeview(editions_frame, columns=cols, show="headings", height=6)

        column_configs = {
            "title": {"width": 250, "anchor": "w"},
            "authors": {"width": 200, "anchor": "w"},
            "isbn": {"width": 120, "anchor": "w"},
            "year": {"width": 80, "anchor": "w"},
            "lang": {"width": 15, "anchor": "w"},
            "quality": {"width": 80, "anchor": "w"},
        }
        for c in cols:
            self.editions_tree.heading(c, text=c.capitalize())
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.editions_tree.column(c, width=config["width"], anchor=config["anchor"])

        scrollbar = ttk.Scrollbar(
            editions_frame, orient=tk.VERTICAL, command=self.editions_tree.yview
        )
        self.editions_tree.configure(yscrollcommand=scrollbar.set)
        self.editions_tree.grid(row=0, column=0, sticky="ewns")
        scrollbar.grid(row=0, column=1, sticky="ns")
        editions_frame.rowconfigure(0, weight=1)
        self.editions_tree.bind("<<TreeviewSelect>>", self._on_edition_selected_from_tree)

    # --- MÉTHODE DE DESSIN DE COUVERTURE ---
    def draw_cover(self, canvas: tk.Canvas, data: Union[bytes, None]):
        """Dessine l'image de couverture sur le canvas fourni."""
        canvas.delete("all")
        w, h = GUI_COVER_SIZE
        if not data:
            canvas.create_rectangle(0, 0, w, h, fill="#EEE", outline="")
            canvas.create_text(
                w // 2,
                h // 2,
                text="Aucune\ncouverture",
                fill="#666",
                font=("TkDefaultFont", 10, "bold"),
            )
            return
        try:
            pil = Image.open(BytesIO(data))
            original_size = pil.size
            pil.thumbnail((w, h), Image.Resampling.LANCZOS)
            img = ImageTk.PhotoImage(pil)
            canvas.image = img  # Garder une référence
            canvas.create_image(w // 2, h // 2, image=img)
            info_height = 30
            canvas.create_rectangle(0, h - info_height, w, h, fill="#222222", outline="")
            iw, ih = pil.size
            orig_w, orig_h = original_size
            canvas.create_text(
                w // 2, h - 20, text=f"{iw}x{ih}", fill="white", font=("TkDefaultFont", 8, "bold")
            )
            if (orig_w, orig_h) != (iw, ih):
                canvas.create_text(
                    w // 2,
                    h - 8,
                    text=f"Orig: {orig_w}x{orig_h}",
                    fill="#AAAAAA",
                    font=("TkDefaultFont", 7),
                )
            quality = "HD" if orig_w >= 800 and orig_h >= 1200 else "SD"
            color = "#00FF00" if quality == "HD" else "#FFAA00"
            canvas.create_text(
                10, 10, text=quality, fill=color, font=("TkDefaultFont", 8, "bold"), anchor="nw"
            )
        except Exception:
            logger.exception("Erreur rendu couverture")
            canvas.create_rectangle(0, 0, w, h, fill="#FFEEEE", outline="")
            canvas.create_text(
                w // 2,
                h // 2,
                text="Erreur\nimage",
                fill="#CC0000",
                font=("TkDefaultFont", 9, "bold"),
            )

    # --- CHARGEMENT / SAUVEGARDE ---
    def load_meta(self, meta: Union["EpubMeta", None]):
        """Charge un objet EpubMeta dans les widgets de comparaison."""
        self.current_meta = meta
        if meta is None:
            self.clear_details()
            return

        self._load_meta_fields(meta)
        self._load_summary_field(meta)

        self.draw_cover(self.cover_orig_canvas, meta.original_cover_data)
        self.draw_cover(self.cover_final_canvas, meta.suggested_cover_data)
        self._populate_editions_tree(meta)
        self.update_comparison_colors()

    def _load_meta_fields(self, meta: "EpubMeta"):
        """Charge les champs textuels simples."""

        def format_list(items) -> str:
            return ", ".join(items) if items else ""

        fields_to_load = [
            ("title", meta.original_title, meta.suggested_title),
            ("publisher", meta.original_publisher, meta.suggested_publisher),
            ("publication_date", meta.original_publication_date, meta.suggested_publication_date),
            ("isbn", meta.original_isbn, meta.suggested_isbn),
            ("language", meta.original_language, meta.suggested_language),
        ]
        for field, orig_val, final_val in fields_to_load:
            if field in self.detail_vars:
                self.detail_vars[field]["orig"].set(orig_val or "")
                self.detail_vars[field]["final"].set(final_val or "")

        # Champs de liste
        if "authors" in self.detail_vars:
            self.detail_vars["authors"]["orig"].set(format_list(meta.original_authors))
            self.detail_vars["authors"]["final"].set(format_list(meta.suggested_authors))
        if "tags" in self.detail_vars:
            self.detail_vars["tags"]["orig"].set(format_list(meta.original_tags))
            self.detail_vars["tags"]["final"].set(format_list(meta.suggested_tags))

    def _load_summary_field(self, meta: "EpubMeta"):
        """Charge le champ résumé (widget Text)."""
        if "summary" not in self.detail_entries:
            return

        orig_text = self.detail_entries["summary"]["orig"]
        orig_text.config(state="normal")
        orig_text.delete(1.0, tk.END)
        orig_text.insert(1.0, meta.original_summary or "")
        orig_text.config(state="disabled")

        final_text = self.detail_entries["summary"]["final"]
        final_text.delete(1.0, tk.END)
        final_text.insert(1.0, meta.suggested_summary or "")

    def clear_details(self):
        """Vide tous les champs de détails."""
        self.current_meta = None
        for field, vars_dict in self.detail_vars.items():
            if vars_dict["orig"] is not None:
                vars_dict["orig"].set("")
            if vars_dict["final"] is not None:
                vars_dict["final"].set("")

        if "summary" in self.detail_entries:
            self.detail_entries["summary"]["orig"].config(state="normal")
            self.detail_entries["summary"]["orig"].delete(1.0, tk.END)
            self.detail_entries["summary"]["orig"].config(state="disabled")
            self.detail_entries["summary"]["final"].delete(1.0, tk.END)

        self.update_comparison_colors()
        self.draw_cover(self.cover_orig_canvas, None)
        self.draw_cover(self.cover_final_canvas, None)
        if self.editions_tree:
            self._populate_editions_tree(None)

    def save_final_values_to_model(self):
        """Sauvegarde les valeurs "finales" de l'interface vers l'objet meta."""
        if not self.current_meta:
            return

        def to_list(val: str) -> List[str]:
            stripped_val = val.strip()
            if not stripped_val:
                return []
            return [v.strip() for v in stripped_val.split(",") if v.strip()]

        # Déléguer à des sous-méthodes
        self._save_text_fields(self.current_meta, to_list)
        self._save_summary_field(self.current_meta)

        # Appliquer les valeurs par défaut si le champ suggéré est vide
        meta = self.current_meta
        meta.suggested_title = meta.suggested_title or meta.original_title
        meta.suggested_authors = meta.suggested_authors or meta.original_authors
        meta.suggested_publisher = meta.suggested_publisher or meta.original_publisher
        meta.suggested_isbn = meta.suggested_isbn or meta.original_isbn
        meta.suggested_language = meta.suggested_language or meta.original_language
        meta.suggested_publication_date = (
            meta.suggested_publication_date or meta.original_publication_date
        )
        meta.suggested_tags = meta.suggested_tags or meta.original_tags
        meta.suggested_summary = meta.suggested_summary or meta.original_summary

        logger.debug("Saved final values from GUI to model for %s", meta.filename)

    def _save_text_fields(self, meta: "EpubMeta", to_list_func: Callable):
        """Sauvegarde les champs textuels simples depuis les StringVars."""
        meta.suggested_title = self.detail_vars["title"]["final"].get().strip()
        meta.suggested_publisher = self.detail_vars["publisher"]["final"].get().strip()
        meta.suggested_isbn = self.detail_vars["isbn"]["final"].get().strip()
        meta.suggested_language = self.detail_vars["language"]["final"].get().strip()
        meta.suggested_publication_date = (
            self.detail_vars["publication_date"]["final"].get().strip()
        )

        # Listes
        final_authors_str = self.detail_vars["authors"]["final"].get()
        meta.suggested_authors = to_list_func(final_authors_str)
        final_tags_str = self.detail_vars["tags"]["final"].get()
        meta.suggested_tags = to_list_func(final_tags_str)

    def _save_summary_field(self, meta: "EpubMeta"):
        """Sauvegarde le champ résumé (widget Text)."""
        if "summary" in self.detail_entries:
            final_summary = self.detail_entries["summary"]["final"].get(1.0, tk.END).strip()
            meta.suggested_summary = final_summary

    def update_comparison_colors(self):
        """Met à jour les couleurs de fond pour montrer les différences."""
        style = ttk.Style()
        style.configure("OrigDiff.TEntry", fieldbackground="#FFDDDD")
        style.configure("FinalDiff.TEntry", fieldbackground="#DDFFDD")
        TEXT_ORIG_DIFF_BG = "#FFDDDD"
        TEXT_FINAL_DIFF_BG = "#DDFFDD"
        TEXT_DEFAULT_BG = "white"  # ou self.default_entry_bg

        for field, vars_dict in self.detail_vars.items():
            if field not in self.detail_entries:
                continue

            orig_entry = self.detail_entries[field]["orig"]
            final_entry = self.detail_entries[field]["final"]
            is_text_widget = isinstance(orig_entry, tk.Text)

            orig_val = ""
            final_val = ""

            if is_text_widget:
                orig_val = orig_entry.get(1.0, tk.END).strip()
                final_val = final_entry.get(1.0, tk.END).strip()
            else:
                orig_val = vars_dict["orig"].get().strip()
                final_val = vars_dict["final"].get().strip()

            if final_val and orig_val != final_val:
                if is_text_widget:
                    orig_entry.configure(background=TEXT_ORIG_DIFF_BG)
                    final_entry.configure(background=TEXT_FINAL_DIFF_BG)
                else:
                    orig_entry.configure(style="OrigDiff.TEntry")
                    final_entry.configure(style="FinalDiff.TEntry")
            else:
                if is_text_widget:
                    orig_entry.configure(background=TEXT_DEFAULT_BG)
                    final_entry.configure(background=TEXT_DEFAULT_BG)
                else:
                    orig_entry.configure(style="TEntry")
                    final_entry.configure(style="TEntry")

    # --- GESTION DES ÉDITIONS ---
    def _populate_editions_tree(self, meta: Union["EpubMeta", None]):
        """Remplit le Treeview des éditions trouvées."""
        if not self.editions_tree:
            return
        self.editions_tree.delete(*self.editions_tree.get_children())
        if not meta or not hasattr(meta, "found_editions") or not meta.found_editions:
            self.editions_tree.insert(
                "", "end", iid="0", values=("Aucune autre édition trouvée.", "", "", "", "")
            )
            return

        for i, doc in enumerate(meta.found_editions):
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
            isbn_list = details.get("isbn_13", []) + details.get("isbn_10", [])
            isbns = ", ".join(isbn_list[:2] or doc.get("isbn", [])[:2])
            year = (
                details.get("publish_date")
                or str(details.get("first_publish_year", ""))
                or str(doc.get("first_publish_year", ""))
            )
            lang = details.get("language", doc.get("language", ""))
            quality_score = 0
            if title:
                quality_score += 20
            if authors:
                quality_score += 20
            if isbns:
                quality_score += 20
            if details.get("publishers") or doc.get("publisher"):
                quality_score += 20
            if year:
                quality_score += 10
            if lang:
                quality_score += 10
            quality_text = f"{quality_score}%"
            self.editions_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(title, authors, isbns, year, lang, quality_text),
            )

    def _on_edition_selected_from_tree(self, event=None):
        """Appelé lors de la sélection d'une édition dans l'arbre."""
        if not self.current_meta or not self.editions_tree:
            return
        selection = self.editions_tree.selection()
        if not selection:
            return

        selected_index = int(selection[0])
        if not hasattr(self.current_meta, "found_editions") or selected_index >= len(
            self.current_meta.found_editions
        ):
            logger.warning("Index d'édition non valide ou 'found_editions' manquant.")
            return

        selected_doc = self.current_meta.found_editions[selected_index]
        self._apply_doc_to_final_fields(selected_doc)
        self.update_comparison_colors()

        # Demander au contrôleur principal de retélécharger la couverture
        if self.current_meta.suggested_cover_data and self.on_edition_selected_cover:
            self.on_edition_selected_cover(self.current_meta)

    def _apply_doc_to_final_fields(self, doc: Dict):
        """Applique les champs d'un document (édition) aux champs 'final'."""
        if not self.current_meta:
            return
        meta = self.current_meta
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
        isbns = ", ".join(isbn_list[:1] or doc.get("isbn", [])[:1])
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
        tags = details.get("subject", doc.get("subject", []))
        cover_data = details.get("cover", doc.get("cover"))

        self.detail_vars["title"]["final"].set(title or "")
        self.detail_vars["authors"]["final"].set(", ".join(authors_list or []))
        self.detail_vars["publisher"]["final"].set(publisher or "")
        self.detail_vars["isbn"]["final"].set(isbns or "")
        self.detail_vars["language"]["final"].set(lang or "")
        self.detail_vars["publication_date"]["final"].set(year or "")
        self.detail_vars["tags"]["final"].set(", ".join(tags or []))
        meta.suggested_cover_data = cover_data
