# epub_enricher/src/epub_enricher/gui/main_window.py
"""
Interface utilisateur principale avec Tkinter
"""

import csv
import logging
import os
import threading
import tkinter as tk
from io import BytesIO
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Dict, List

from PIL import Image

from ..config import GUI_COVER_SIZE, GUI_GEOMETRY, GUI_TITLE, GUI_TREE_HEIGHT
from ..core.epub_processor import extract_metadata, find_epubs_in_folder, update_epub_with_metadata
from ..core.metadata_fetcher import download_cover, fetch_genre_and_summary, query_openlibrary_full
from ..core.models import EpubMeta

if TYPE_CHECKING:
    # Imported only for type checking to avoid runtime dependency in headless envs
    from PIL import ImageTk  # noqa: F401

logger = logging.getLogger(__name__)


class EnricherGUI(tk.Tk):
    """Interface graphique principale pour EPUB Enricher."""

    def __init__(self):
        super().__init__()
        self.title(GUI_TITLE)
        self.geometry(GUI_GEOMETRY)
        self.meta_list: List[EpubMeta] = []
        # MODIFIÉ : Le cache utilisera les données binaires comme clé pour plus de robustesse
        self.cover_photo_cache: Dict[bytes, "ImageTk.PhotoImage"] = {}
        self.current_meta: EpubMeta | None = None

        self.detail_vars: Dict[str, Dict[str, tk.StringVar]] = {}
        self.detail_entries: Dict[str, Dict[str, ttk.Entry]] = {}

        self.create_widgets()

        s = ttk.Style()
        self.default_entry_bg = s.lookup("TEntry", "fieldbackground")

    def create_widgets(self):
        frm_top = ttk.Frame(self)
        frm_top.pack(fill=tk.X, padx=6, pady=6)

        self.folder_var = tk.StringVar()
        ttk.Entry(frm_top, textvariable=self.folder_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Select folder", command=self.select_folder).pack(side=tk.LEFT)
        ttk.Button(frm_top, text="Scan", command=self.scan_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            frm_top, text="Fetch suggestions", command=self.fetch_suggestions_for_selected
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Apply accepted", command=self.apply_accepted).pack(
            side=tk.LEFT, padx=4
        )

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

        # Configuration des colonnes avec largeurs optimisées
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
            self.tree.heading(c, text=c.replace("_", " ").capitalize())
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            self.tree.column(c, width=config["width"], anchor=config["anchor"])
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(bottom)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Zone de comparaison et sélection ---
        frm_comparison = ttk.LabelFrame(left, text="Comparaison et Sélection")
        frm_comparison.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Configuration des colonnes pour équilibrer
        frm_comparison.columnconfigure(1, weight=1)  # Champ
        frm_comparison.columnconfigure(2, weight=2)  # Valeur originale
        frm_comparison.columnconfigure(3, weight=1)  # Bouton utiliser
        frm_comparison.columnconfigure(4, weight=2)  # Valeur finale

        # --- Covers : fixées sur la gauche et la droite ---
        self.cover_orig_canvas = tk.Canvas(
            frm_comparison,
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
            frm_comparison,
            width=GUI_COVER_SIZE[0],
            height=GUI_COVER_SIZE[1],
            bg="#EEE",
            highlightthickness=2,
            highlightbackground="#004488",
            relief="raised",
            bd=2,
        )
        self.cover_final_canvas.grid(row=1, column=5, rowspan=20, padx=6, pady=6, sticky="n")

        # Labels pour les couvertures
        self.cover_orig_label = ttk.Label(
            frm_comparison, text="Couverture originale", font=("TkDefaultFont", 9, "bold")
        )
        self.cover_orig_label.grid(row=0, column=0, padx=6, pady=3, sticky="w")

        self.cover_final_label = ttk.Label(
            frm_comparison, text="Couverture suggérée", font=("TkDefaultFont", 9, "bold")
        )
        self.cover_final_label.grid(row=0, column=5, padx=6, pady=3, sticky="w")

        # --- En-têtes de colonnes ---
        ttk.Label(frm_comparison, text="Champ", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=1, padx=5, pady=3, sticky="w"
        )
        ttk.Label(frm_comparison, text="Original", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=2, padx=5, pady=3, sticky="w"
        )
        ttk.Label(
            frm_comparison, text="Valeur à appliquer", font=("TkDefaultFont", 10, "bold")
        ).grid(row=0, column=4, padx=5, pady=3, sticky="w")

        # --- Champs dynamiques ---
        fields = [
            "title",
            "authors",
            "publisher",
            "isbn",
            "language",
            "publication_date",
            "genre",
            "summary",
            "tags",
        ]
        for i, field in enumerate(fields, start=1):
            field_label = field.replace("_", " ").capitalize()
            ttk.Label(frm_comparison, text=field_label).grid(
                row=i, column=1, padx=5, pady=5, sticky="w"
            )

            self.detail_vars[field] = {"orig": tk.StringVar(), "final": tk.StringVar()}
            self.detail_entries[field] = {}

            # Widget spécial pour le résumé (zone de texte)
            if field == "summary":
                # Zone de texte pour l'original (lecture seule)
                orig_text = tk.Text(
                    frm_comparison, height=3, width=30, state="disabled", wrap=tk.WORD
                )
                orig_text.grid(row=i, column=2, sticky="ew", padx=5)
                self.detail_entries[field]["orig"] = orig_text

                # Zone de texte pour la valeur finale (éditable)
                final_text = tk.Text(frm_comparison, height=3, width=30, wrap=tk.WORD)
                final_text.grid(row=i, column=4, sticky="ew", padx=5)
                self.detail_entries[field]["final"] = final_text
            else:
                # Entrées normales pour les autres champs
                orig_entry = ttk.Entry(
                    frm_comparison, textvariable=self.detail_vars[field]["orig"], state="readonly"
                )
                orig_entry.grid(row=i, column=2, sticky="ew", padx=5)
                self.detail_entries[field]["orig"] = orig_entry

                final_entry = ttk.Entry(
                    frm_comparison, textvariable=self.detail_vars[field]["final"]
                )
                final_entry.grid(row=i, column=4, sticky="ew", padx=5)
                self.detail_entries[field]["final"] = final_entry

            # Bouton utiliser intégré dans sa colonne (col=3)
            use_btn = ttk.Button(
                frm_comparison,
                text="→",
                width=4,
                command=lambda f=field: self.choose_field(f, "orig"),
            )
            use_btn.grid(row=i, column=3, padx=2, pady=2)

        # --- Bouton utiliser cover (sous l’image gauche) ---
        self.cover_use_button = ttk.Button(
            frm_comparison,
            text="Utiliser cette couverture →",
            command=lambda: self.choose_cover("orig"),
        )
        self.cover_use_button.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(10, 6))

        ttk.Button(right, text="Accept suggestion", command=self.accept_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Reject suggestion", command=self.reject_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Save CSV", command=self.export_csv).pack(fill=tk.X, padx=4, pady=8)

    def select_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.folder_var.set(d)

    def scan_folder(self):
        folder = self.folder_var.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Select a valid folder first")
            return
        files = find_epubs_in_folder(folder)
        self.meta_list = []
        for p in files:
            # MODIFIÉ : On s'attend à ce que extract_metadata retourne aussi
            # "cover_data" et les métadonnées de contenu
            res = extract_metadata(p)
            em = EpubMeta(
                path=p,
                filename=os.path.basename(p),
                original_title=res.get("title"),
                original_authors=res.get("authors"),
                original_isbn=res.get("identifier"),
                original_language=res.get("language"),
                original_tags=res.get("tags"),
                original_publisher=res.get("publisher"),
                original_publication_date=res.get("date"),
                # NOUVEAU : Stockage des données de la couverture originale
                original_cover_data=res.get("cover_data"),
                # NOUVEAU : Métadonnées extraites du contenu
                content_isbn=res.get("content_isbn"),
                content_summary=res.get("content_summary"),
                content_genre=res.get("content_genre"),
                content_publisher=res.get("content_publisher"),
                content_publication_date=res.get("content_publication_date"),
                content_edition_info=res.get("content_edition_info"),
                content_analysis=res.get("content_analysis"),
            )
            self.meta_list.append(em)
        self.refresh_tree()
        self.clear_details()

    def clear_details(self):
        """Vide les champs de la vue détaillée et les couvertures."""
        for field_vars in self.detail_vars.values():
            field_vars["orig"].set("")
            field_vars["final"].set("")

        self.update_comparison_colors()

        # ✅ Nettoyer les canvases de couverture
        w, h = GUI_COVER_SIZE
        for canvas in (self.cover_orig_canvas, self.cover_final_canvas):
            canvas.delete("all")
            canvas.create_rectangle(0, 0, w, h, fill="#EEE", outline="")
            canvas.create_text(
                w // 2,
                h // 2,
                text="Aucune\ncouverture",
                fill="#666",
                font=("TkDefaultFont", 10, "bold"),
            )

        self.current_meta = None

    def _calculate_metadata_quality(self, meta) -> int:
        """Calcule un score de qualité des métadonnées (0-100%)."""
        score = 0
        total_fields = 9  # title, authors, publisher, isbn, language, date, genre, summary, tags

        # Vérifier les métadonnées suggérées (priorité)
        if meta.suggested_title:
            score += 1
        if meta.suggested_authors:
            score += 1
        if meta.suggested_publisher:
            score += 1
        if meta.suggested_isbn:
            score += 1
        if meta.suggested_language:
            score += 1
        if meta.suggested_publication_date:
            score += 1
        if meta.suggested_tags:
            score += 1
        if meta.suggested_genre:
            score += 1
        if meta.suggested_summary:
            score += 1

        # Si pas de suggestions, vérifier les originales ou le contenu
        if not meta.suggested_title and meta.original_title:
            score += 1
        if not meta.suggested_authors and meta.original_authors:
            score += 1
        if not meta.suggested_publisher and meta.original_publisher:
            score += 1
        if not meta.suggested_isbn and meta.original_isbn:
            score += 1
        if not meta.suggested_language and meta.original_language:
            score += 1
        if not meta.suggested_publication_date and meta.original_publication_date:
            score += 1
        if not meta.suggested_tags and meta.original_tags:
            score += 1
        if not meta.suggested_genre and (meta.content_genre or meta.original_tags):
            score += 1
        if not meta.suggested_summary and meta.content_summary:
            score += 1

        return int((score / total_fields) * 100)

    def refresh_tree(self):
        selected_ids = self.tree.selection()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, m in enumerate(self.meta_list):
            # Calculer la qualité des métadonnées
            quality_score = self._calculate_metadata_quality(m)
            status_text = "accepted" if m.accepted else ("processed" if m.processed else "idle")
            if quality_score > 0:
                status_text += f" ({quality_score}%)"

            # Aperçu du résumé (limité à 50 caractères)
            summary_preview = ""
            if m.suggested_summary or m.content_summary:
                summary_text = m.suggested_summary or m.content_summary or ""
                if len(summary_text) > 50:
                    summary_preview = summary_text[:50] + "..."
                else:
                    summary_preview = summary_text

            vals = (
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
            self.tree.insert("", "end", iid=str(idx), values=vals)
        if selected_ids:
            self.tree.selection_set(selected_ids)

    def on_select(self, evt=None):
        sel = self.tree.selection()
        if not sel:
            self.clear_details()
            return
        idx = int(sel[0])
        meta = self.meta_list[idx]
        self.current_meta = meta

        def format_list(items: List[str] | None) -> str:
            return ", ".join(items) if items else ""

        # Champs de base
        self.detail_vars["title"]["orig"].set(meta.original_title or "")
        self.detail_vars["authors"]["orig"].set(format_list(meta.original_authors))
        self.detail_vars["publisher"]["orig"].set(meta.original_publisher or "")
        self.detail_vars["publication_date"]["orig"].set(meta.original_publication_date or "")
        self.detail_vars["isbn"]["orig"].set(meta.original_isbn or "")
        self.detail_vars["language"]["orig"].set(meta.original_language or "")
        self.detail_vars["tags"]["orig"].set(format_list(meta.original_tags))

        # NOUVEAU : Champs de contenu
        self.detail_vars["genre"]["orig"].set(meta.content_genre or "")
        self.detail_vars["summary"]["orig"].set(meta.content_summary or "")

        # Valeurs suggérées
        self.detail_vars["title"]["final"].set(meta.suggested_title or "")
        self.detail_vars["authors"]["final"].set(format_list(meta.suggested_authors))
        self.detail_vars["publisher"]["final"].set(meta.suggested_publisher or "")
        self.detail_vars["publication_date"]["final"].set(meta.suggested_publication_date or "")
        self.detail_vars["isbn"]["final"].set(meta.suggested_isbn or "")
        self.detail_vars["language"]["final"].set(meta.suggested_language or "")
        self.detail_vars["tags"]["final"].set(format_list(meta.suggested_tags))
        self.detail_vars["genre"]["final"].set(meta.suggested_genre or "")

        # Gestion spéciale du résumé (zone de texte)
        if "summary" in self.detail_entries:
            # Original
            orig_text = self.detail_entries["summary"]["orig"]
            orig_text.config(state="normal")
            orig_text.delete(1.0, tk.END)
            orig_text.insert(1.0, meta.content_summary or "")
            orig_text.config(state="disabled")

            # Final
            final_text = self.detail_entries["summary"]["final"]
            final_text.delete(1.0, tk.END)
            final_text.insert(1.0, meta.suggested_summary or "")

        self.update_comparison_colors()

        self.draw_cover(self.cover_orig_canvas, meta.original_cover_data)
        self.draw_cover(self.cover_final_canvas, meta.suggested_cover_data)

    def update_comparison_colors(self):
        """Met à jour les couleurs de fond des champs de comparaison."""
        style = ttk.Style()
        # Les styles customisés sont toujours nécessaires pour les TEntry
        style.configure("OrigDiff.TEntry", fieldbackground="#FFDDDD")  # Rouge clair
        style.configure("FinalDiff.TEntry", fieldbackground="#DDFFDD")  # Vert clair

        # Définition des couleurs de fond pour tk.Text / tk.Entry non-ttk
        TEXT_ORIG_DIFF_BG = "#FFDDDD"
        TEXT_FINAL_DIFF_BG = "#DDFFDD"
        TEXT_DEFAULT_BG = "white"  # Les widgets tk.Text ont un fond blanc par défaut

        for field, vars_dict in self.detail_vars.items():
            orig_val = vars_dict["orig"].get()
            final_val = vars_dict["final"].get()

            orig_entry = self.detail_entries[field]["orig"]
            final_entry = self.detail_entries[field]["final"]

            is_text_widget = isinstance(orig_entry, tk.Text)

            if final_val and orig_val != final_val:
                # S'ils diffèrent -> mettre couleurs custom
                if is_text_widget:
                    # Pour tk.Text, on configure directement l'option 'background'
                    orig_entry.configure(background=TEXT_ORIG_DIFF_BG)
                    final_entry.configure(background=TEXT_FINAL_DIFF_BG)
                else:
                    # Pour ttk.Entry, on configure le 'style'
                    orig_entry.configure(style="OrigDiff.TEntry")
                    final_entry.configure(style="FinalDiff.TEntry")
            else:
                # Sinon, revenir au style par défaut
                if is_text_widget:
                    # Pour tk.Text, on revient au blanc par défaut
                    orig_entry.configure(background=TEXT_DEFAULT_BG)
                    final_entry.configure(background=TEXT_DEFAULT_BG)
                else:
                    # Pour ttk.Entry, on revient au style par défaut de TEntry
                    orig_entry.configure(style="TEntry")
                    final_entry.configure(style="TEntry")

    def choose_field(self, field: str, side: str):
        """Applique la valeur originale au champ 'final'."""
        if not self.current_meta:
            return
        if side == "orig":
            if field == "summary":
                # Gestion spéciale pour le résumé
                content_summary = getattr(self.current_meta, f"content_{field}", None)
                setattr(self.current_meta, f"suggested_{field}", content_summary)
            elif field == "genre":
                # Gestion spéciale pour le genre
                content_genre = getattr(self.current_meta, f"content_{field}", None)
                setattr(self.current_meta, f"suggested_{field}", content_genre)
            else:
                # Gestion normale pour les autres champs
                original_value = getattr(self.current_meta, f"original_{field}")
                setattr(self.current_meta, f"suggested_{field}", original_value)
        self.refresh_tree()
        self.on_select(None)

    def choose_cover(self, side: str):
        """Applique la couverture choisie (originale) à la valeur 'finale'."""
        if not self.current_meta:
            return
        if side == "orig":
            # On copie les données de l'image originale vers le champ de suggestion
            self.current_meta.suggested_cover_data = self.current_meta.original_cover_data

        # Rafraîchir l'affichage pour voir le changement immédiatement
        self.on_select(None)

    def get_cover_photo(self, data: bytes | None) -> "ImageTk.PhotoImage | None":
        if not data:
            return None
        if data in self.cover_photo_cache:
            return self.cover_photo_cache[data]
        try:
            from PIL import ImageTk
        except ImportError:
            logger.error("Pillow est requis pour afficher les images. `pip install Pillow`")
            return None
        try:
            pil = Image.open(BytesIO(data))
            pil.thumbnail(GUI_COVER_SIZE)
            tkimg = ImageTk.PhotoImage(pil)
            self.cover_photo_cache[data] = tkimg
            return tkimg
        except Exception:
            logger.exception("Échec de la création de l'aperçu d'image à partir des données")
            return None

    def show_related_editions(self, docs: List[Dict]):
        """Affiche dans une nouvelle fenêtre toutes les éditions trouvées sur OpenLibrary."""
        win = tk.Toplevel(self)
        win.title("Éditions disponibles")
        win.geometry("1200x400")

        # Frame principal avec scrollbar
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Informations sur le nombre d'éditions
        info_label = ttk.Label(
            main_frame,
            text=f"Trouvé {len(docs)} édition(s) sur OpenLibrary",
            font=("TkDefaultFont", 10, "bold"),
        )
        info_label.pack(pady=(0, 10))

        # Treeview avec scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("title", "authors", "language", "isbn", "publisher", "year", "quality")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")

        # Configuration des colonnes
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
            tree.heading(c, text=c.capitalize())
            config = column_configs.get(c, {"width": 120, "anchor": "w"})
            tree.column(c, width=config["width"], anchor=config["anchor"])

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for i, doc in enumerate(docs):
            # 💡 Début des modifications pour extraire des détails plus précis
            details = doc.get("edition_details") or doc.get("work_details") or doc

            # Utilise les détails précis ou revient à la valeur de la recherche (doc)
            title = details.get("title", doc.get("title", ""))

            # Auteurs (plus complexes car les formats sont variés)
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

            # Langue (extrait des objets si disponible)
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
                lang = ", ".join(langs_obj or [])  # S'il s'agit d'une liste de strings

            # ISBNs (combine 13 et 10)
            isbn_list = details.get("isbn_13", []) + details.get("isbn_10", [])
            isbns = ", ".join(isbn_list[:2] or doc.get("isbn", [])[:2])

            # Éditeur (supporte la liste de noms ou la liste d'objets)
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

            # Année/Date
            year = (
                details.get("publish_date")
                or str(details.get("first_publish_year", ""))
                or str(doc.get("first_publish_year", ""))
            )

            # Calculer un score de qualité
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

            tree.insert(
                "", "end", values=(title, authors, lang, isbns, publisher, year, quality_text)
            )

        # Boutons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Fermer", command=win.destroy).pack(side=tk.RIGHT)
        ttk.Button(
            button_frame,
            text="Sélectionner cette édition",
            command=lambda: self._select_edition_from_list(tree, docs),
        ).pack(side=tk.LEFT)

    def _select_edition_from_list(self, tree, docs):
        """Sélectionne une édition depuis la liste des éditions disponibles."""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une édition")
            return

        # Récupérer l'édition sélectionnée
        item = tree.item(selection[0])
        values = item["values"]
        title = values[0]

        # Trouver l'édition correspondante dans la liste
        selected_doc = None
        for doc in docs:
            if doc.get("title", "") == title:
                selected_doc = doc
                break

        if not selected_doc:
            messagebox.showerror("Erreur", "Édition non trouvée")
            return

        # Appliquer les métadonnées de l'édition sélectionnée
        if self.current_meta:
            self.current_meta.suggested_title = selected_doc.get("title")
            self.current_meta.suggested_authors = selected_doc.get("author_name", [])
            self.current_meta.suggested_publisher = ", ".join(selected_doc.get("publisher", []))
            # Premier ISBN seulement
            self.current_meta.suggested_isbn = ", ".join(selected_doc.get("isbn", [])[:1])
            self.current_meta.suggested_language = ", ".join(selected_doc.get("language", []))
            self.current_meta.suggested_publication_date = str(
                selected_doc.get("first_publish_year", "")
            )
            self.current_meta.suggested_tags = selected_doc.get("subject", [])

            # Mettre à jour l'affichage
            self.refresh_tree()
            self.on_select(None)

            messagebox.showinfo("Succès", f"Édition sélectionnée : {title}")

        # Fermer la fenêtre des éditions
        tree.master.master.destroy()

    def fetch_suggestions_for_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select one or more files in the list")
            return
        threading.Thread(target=self._fetch_thread, args=(sel,), daemon=True).start()

    def _fetch_thread(self, selection):
        changed = False
        for s in selection:
            idx = int(s)
            meta = self.meta_list[idx]
            try:
                res = query_openlibrary_full(
                    title=meta.original_title,
                    authors=meta.original_authors,
                    isbn=meta.original_isbn,
                )

                suggested = {}
                if res.get("by_isbn"):
                    suggested = res["by_isbn"]
                elif res.get("related_docs"):
                    suggested = res["related_docs"][0]

                meta.suggested_title = suggested.get("title")
                meta.suggested_authors = suggested.get("authors") or suggested.get("author_name")
                meta.suggested_isbn = suggested.get("isbn")
                meta.suggested_language = suggested.get("language")
                meta.suggested_publisher = suggested.get("publisher")
                meta.suggested_publication_date = suggested.get("publish_date") or suggested.get(
                    "first_publish_year"
                )
                meta.suggested_tags = suggested.get("subject") or []

                meta.suggested_cover_url = suggested.get("cover")
                if meta.suggested_cover_url:
                    meta.suggested_cover_data = download_cover(meta.suggested_cover_url)
                else:
                    meta.suggested_cover_data = None

                # --- NOUVEAU : récupération du genre et du résumé ---
                try:
                    genre_summary_data = fetch_genre_and_summary(
                        title=meta.original_title,
                        authors=meta.original_authors,
                        isbn=meta.original_isbn,
                    )

                    # Appliquer le genre et le résumé suggérés
                    if genre_summary_data.get("genre"):
                        meta.suggested_genre = genre_summary_data["genre"]
                    if genre_summary_data.get("summary"):
                        meta.suggested_summary = genre_summary_data["summary"]

                    logger.debug(
                        "Fetched genre and summary for %s: genre=%s, summary=%s",
                        meta.filename,
                        meta.suggested_genre or "None",
                        "Yes" if meta.suggested_summary else "No",
                    )

                except Exception as e:
                    logger.warning("Failed to fetch genre and summary for %s: %s", meta.filename, e)

                # --- NOUVEAU : affichage des éditions disponibles ---
                related_docs = res.get("related_docs", [])
                if related_docs:
                    self.after(0, self.show_related_editions, related_docs)

                # --- ANCIEN CODE : marquage et mise à jour de l'état ---
                meta.processed = True
                meta.note = "Suggestion fetched"
                changed = True
                logger.debug("Fetched suggestion for %s", meta.filename)

            except Exception as e:
                meta.note = f"Fetch error: {e}"
                logger.exception("Fetch suggestions error for %s", meta.filename)

        if changed:
            self.after(0, self.refresh_tree)
            current_selection = self.tree.selection()
            if current_selection and current_selection[0] in selection:
                self.after(0, self.on_select, None)

    def accept_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            idx = int(s)
            meta = self.meta_list[idx]
            if meta.processed:
                meta.accepted = True
        self.refresh_tree()

    def reject_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            idx = int(s)
            meta = self.meta_list[idx]
            meta.accepted = False
            meta.suggested_title = None
            meta.suggested_authors = []
            meta.suggested_isbn = None
            meta.suggested_language = None
            meta.suggested_tags = []
            meta.suggested_publisher = None
            meta.suggested_publication_date = None
            meta.suggested_cover_url = None
            # NOUVEAU: Réinitialiser aussi les données de la couverture suggérée
            meta.suggested_cover_data = None
            # NOUVEAU: Réinitialiser le genre et le résumé suggérés
            meta.suggested_genre = None
            meta.suggested_summary = None
            meta.processed = False

        self.refresh_tree()
        current_selection = self.tree.selection()
        if current_selection and current_selection[0] in sel:
            self.after(0, self.on_select, None)

    def apply_accepted(self):
        to_process = [m for m in self.meta_list if m.accepted]
        if not to_process:
            messagebox.showinfo("Info", "No accepted items to apply")
            return
        threading.Thread(target=self._apply_thread, args=(to_process,), daemon=True).start()

    def _apply_thread(self, metas: List[EpubMeta]):
        any_changed = False
        for m in metas:
            try:
                # MODIFIÉ : update_epub_with_metadata doit utiliser m.suggested_cover_data
                success = update_epub_with_metadata(m.path, m)
                m.note = "Updated" if success else (m.note or "Failed")

                if success:
                    # Logique de consolidation après succès
                    m.original_title = m.suggested_title or m.original_title
                    m.original_authors = m.suggested_authors or m.original_authors
                    m.original_isbn = m.suggested_isbn or m.original_isbn
                    m.original_language = m.suggested_language or m.original_language
                    m.original_tags = m.suggested_tags or m.original_tags
                    m.original_publisher = m.suggested_publisher or m.original_publisher
                    m.original_publication_date = (
                        m.suggested_publication_date or m.original_publication_date
                    )
                    # NOUVEAU : Consolider aussi la couverture
                    if m.suggested_cover_data:
                        m.original_cover_data = m.suggested_cover_data

                    # NOUVEAU : Consolider le genre et le résumé
                    if m.suggested_genre:
                        m.content_genre = m.suggested_genre
                    if m.suggested_summary:
                        m.content_summary = m.suggested_summary

                    # Réinitialise l'état du livre
                    m.suggested_title = None
                    m.suggested_authors = []
                    m.suggested_isbn = None
                    m.suggested_language = None
                    m.suggested_tags = []
                    m.suggested_publisher = None
                    m.suggested_publication_date = None
                    m.suggested_cover_url = None
                    m.suggested_cover_data = None
                    m.suggested_genre = None
                    m.suggested_summary = None
                    m.accepted = False
                    m.processed = False
                any_changed = True
            except Exception as e:
                m.note = f"Error applying: {e}"
                logger.exception("Apply accepted failed for %s", m.filename)
        if any_changed:
            self.after(0, self.refresh_tree)
            self.after(0, self.on_select, None)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", "Applied accepted changes (check backup folder if needed)"
                ),
            )

    def export_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "filename",
                    "path",
                    "orig_title",
                    "orig_authors",
                    "orig_tags",
                    "orig_publisher",
                    "orig_date",
                    "orig_isbn",
                    "orig_lang",
                    "content_genre",
                    "content_summary",
                    "sugg_title",
                    "sugg_authors",
                    "sugg_tags",
                    "sugg_publisher",
                    "sugg_date",
                    "sugg_isbn",
                    "sugg_lang",
                    "sugg_genre",
                    "sugg_summary",
                    "accepted",
                    "processed",
                    "note",
                ]
            )
            for m in self.meta_list:
                w.writerow(
                    [
                        m.filename,
                        m.path,
                        m.original_title,
                        ";".join(m.original_authors or []),
                        ";".join(m.original_tags or []),
                        m.original_publisher,
                        m.original_publication_date,
                        m.original_isbn,
                        m.original_language,
                        m.content_genre or "",
                        m.content_summary or "",
                        m.suggested_title,
                        ";".join(m.suggested_authors or []),
                        ";".join(m.suggested_tags or []),
                        m.suggested_publisher,
                        m.suggested_publication_date,
                        m.suggested_isbn,
                        m.suggested_language,
                        m.suggested_genre or "",
                        m.suggested_summary or "",
                        m.accepted,
                        m.processed,
                        m.note,
                    ]
                )

    def draw_cover(self, canvas: tk.Canvas, data: bytes | None):
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
        from PIL import ImageTk

        try:
            pil = Image.open(BytesIO(data))
            original_size = pil.size
            pil.thumbnail((w, h), Image.Resampling.LANCZOS)
            img = ImageTk.PhotoImage(pil)
            canvas.image = img
            canvas.create_image(w // 2, h // 2, image=img)

            # Affichage des informations de qualité
            iw, ih = pil.size
            orig_w, orig_h = original_size

            # Barre d'information en bas
            info_height = 30
            canvas.create_rectangle(0, h - info_height, w, h, fill="#222222", outline="")

            # Taille de l'image redimensionnée
            canvas.create_text(
                w // 2, h - 20, text=f"{iw}x{ih}", fill="white", font=("TkDefaultFont", 8, "bold")
            )

            # Taille originale si différente
            if (orig_w, orig_h) != (iw, ih):
                canvas.create_text(
                    w // 2,
                    h - 8,
                    text=f"Orig: {orig_w}x{orig_h}",
                    fill="#AAAAAA",
                    font=("TkDefaultFont", 7),
                )

            # Indicateur de qualité
            quality = "HD" if orig_w >= 800 and orig_h >= 1200 else "SD"
            color = "#00FF00" if quality == "HD" else "#FFAA00"
            canvas.create_text(10, 10, text=quality, fill=color, font=("TkDefaultFont", 8, "bold"))

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
