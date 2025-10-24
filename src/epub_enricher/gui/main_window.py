# epub_enricher/src/epub_enricher/gui/main_window.py
"""
Interface utilisateur principale avec Tkinter (Contrôleur)
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

# --- NOUVEAUX IMPORTS ---
from .comparison_frame import ComparisonFrame
from .editions_window import EditionsWindow

# -------------------------

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
        self.current_meta: EpubMeta | None = None

        # --- SUPPRIMÉ ---
        # self.detail_vars: Dict[str, Dict[str, tk.StringVar]] = {}
        # self.detail_entries: Dict[str, Dict[str, ttk.Entry]] = {}
        # ---

        # --- AJOUTÉ ---
        self.comparison_frame: ComparisonFrame | None = None
        self.tree: ttk.Treeview | None = None
        # ---

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

        # --- MODIFIÉ : Création du frame de comparaison ---
        # Toute la logique de création des widgets de comparaison est
        # maintenant dans la classe ComparisonFrame.
        self.comparison_frame = ComparisonFrame(left, self)
        self.comparison_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        # --- FIN DE LA MODIFICATION ---

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
                original_cover_data=res.get("cover_data"),
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
        """Vide les champs de la vue détaillée."""
        if self.comparison_frame:
            self.comparison_frame.load_meta(None)
        self.current_meta = None

    def _calculate_metadata_quality(self, meta) -> int:
        """Calcule un score de qualité des métadonnées (0-100%)."""
        # (Logique inchangée)
        score = 0
        total_fields = 9
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
        # (Fin de la logique inchangée)

    def refresh_tree(self):
        selected_ids = self.tree.selection()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, m in enumerate(self.meta_list):
            quality_score = self._calculate_metadata_quality(m)
            status_text = "accepted" if m.accepted else ("processed" if m.processed else "idle")
            if quality_score > 0:
                status_text += f" ({quality_score}%)"

            summary_preview = ""
            if m.suggested_summary or m.content_summary:
                summary_text = m.suggested_summary or m.content_summary or ""
                summary_preview = (
                    (summary_text[:50] + "...") if len(summary_text) > 50 else summary_text
                )

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
            try:
                self.tree.selection_set(selected_ids)
            except tk.TclError:
                pass  # Items n'existent plus

    def on_select(self, evt=None):
        sel = self.tree.selection()
        if not sel:
            self.clear_details()
            return
        idx = int(sel[0])
        meta = self.meta_list[idx]
        self.current_meta = meta

        # --- MODIFIÉ : Délégation au ComparisonFrame ---
        if self.comparison_frame:
            self.comparison_frame.load_meta(meta)
        # --- FIN DE LA MODIFICATION ---

    # --- SUPPRIMÉ ---
    # La méthode update_comparison_colors() a été déplacée
    # dans comparison_frame.py
    # ---

    def choose_field(self, field: str, side: str):
        """Applique la valeur originale au champ 'final'."""
        if not self.current_meta:
            return
        if side == "orig":
            if field == "summary":
                content_summary = getattr(self.current_meta, f"content_{field}", None)
                setattr(self.current_meta, f"suggested_{field}", content_summary)
            elif field == "genre":
                content_genre = getattr(self.current_meta, f"content_{field}", None)
                setattr(self.current_meta, f"suggested_{field}", content_genre)
            else:
                original_value = getattr(self.current_meta, f"original_{field}")
                setattr(self.current_meta, f"suggested_{field}", original_value)
        self.refresh_tree()
        self.on_select(None)  # Rafraîchir la vue de comparaison

    def choose_cover(self, side: str):
        """Applique la couverture choisie (originale) à la valeur 'finale'."""
        if not self.current_meta:
            return
        if side == "orig":
            self.current_meta.suggested_cover_data = self.current_meta.original_cover_data
        self.on_select(None)  # Rafraîchir la vue de comparaison

    def get_cover_photo(self, data: bytes | None) -> "ImageTk.PhotoImage | None":
        # Cette méthode reste ici car elle gère le cache de l'instance
        if not data:
            return None
        if data in self.cover_photo_cache:
            return self.cover_photo_cache[data]
        try:
            from PIL import ImageTk
        except ImportError:
            logger.error("Pillow est requis. `pip install Pillow`")
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

    # --- SUPPRIMÉ ---
    # show_related_editions() a été déplacée dans editions_window.py
    # ---

    # --- SUPPRIMÉ ---
    # _select_edition_from_list() est remplacée par
    # _launch_editions_window() et _on_edition_selected()
    # ---

    # --- NOUVEAU : Méthode pour lancer la fenêtre des éditions ---
    def _launch_editions_window(self, docs: List[Dict]):
        """Ouvre la fenêtre modale des éditions."""
        if not docs:
            return
        # Le callback _on_edition_selected sera appelé lors de la sélection
        EditionsWindow(self, docs, self._on_edition_selected)

    # --- NOUVEAU : Callback pour la sélection d'édition ---
    def _on_edition_selected(self, selected_doc: Dict):
        """Applique les métadonnées de l'édition sélectionnée."""
        if not self.current_meta or not selected_doc:
            return

        title = selected_doc.get("title")
        logger.info(f"Application de l'édition sélectionnée : {title}")

        try:
            self.current_meta.suggested_title = selected_doc.get("title")
            self.current_meta.suggested_authors = selected_doc.get("author_name", [])
            self.current_meta.suggested_publisher = ", ".join(selected_doc.get("publisher", []))
            self.current_meta.suggested_isbn = ", ".join(selected_doc.get("isbn", [])[:1])
            self.current_meta.suggested_language = ", ".join(selected_doc.get("language", []))
            self.current_meta.suggested_publication_date = str(
                selected_doc.get("first_publish_year", "")
            )
            self.current_meta.suggested_tags = selected_doc.get("subject", [])

            self.refresh_tree()
            self.on_select(None)

            messagebox.showinfo("Succès", f"Édition sélectionnée : {title}")
        except Exception as e:
            logger.exception("Erreur lors de l'application de l'édition sélectionnée")
            messagebox.showerror("Erreur", f"Impossible d'appliquer l'édition : {e}")

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

                try:
                    genre_summary_data = fetch_genre_and_summary(
                        title=meta.original_title,
                        authors=meta.original_authors,
                        isbn=meta.original_isbn,
                    )
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

                # --- MODIFIÉ : Lancement de la fenêtre pop-up ---
                related_docs = res.get("related_docs", [])
                if related_docs:
                    # On utilise self.after() pour appeler la GUI depuis ce thread
                    self.after(0, self._launch_editions_window, related_docs)
                # --- FIN DE LA MODIFICATION ---

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
        # (Logique inchangée)
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
        # (Logique inchangée)
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
            meta.suggested_cover_data = None
            meta.suggested_genre = None
            meta.suggested_summary = None
            meta.processed = False
        self.refresh_tree()
        current_selection = self.tree.selection()
        if current_selection and current_selection[0] in sel:
            self.after(0, self.on_select, None)

    def apply_accepted(self):
        # (Logique inchangée)
        to_process = [m for m in self.meta_list if m.accepted]
        if not to_process:
            messagebox.showinfo("Info", "No accepted items to apply")
            return
        threading.Thread(target=self._apply_thread, args=(to_process,), daemon=True).start()

    def _apply_thread(self, metas: List[EpubMeta]):
        # (Logique inchangée)
        any_changed = False
        for m in metas:
            try:
                success = update_epub_with_metadata(m.path, m)
                m.note = "Updated" if success else (m.note or "Failed")
                if success:
                    m.original_title = m.suggested_title or m.original_title
                    m.original_authors = m.suggested_authors or m.original_authors
                    m.original_isbn = m.suggested_isbn or m.original_isbn
                    m.original_language = m.suggested_language or m.original_language
                    m.original_tags = m.suggested_tags or m.original_tags
                    m.original_publisher = m.suggested_publisher or m.original_publisher
                    m.original_publication_date = (
                        m.suggested_publication_date or m.original_publication_date
                    )
                    if m.suggested_cover_data:
                        m.original_cover_data = m.suggested_cover_data
                    if m.suggested_genre:
                        m.content_genre = m.suggested_genre
                    if m.suggested_summary:
                        m.content_summary = m.suggested_summary

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
        # (Logique inchangée)
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
        # Cette méthode reste dans le contrôleur principal car elle est
        # appelée par ComparisonFrame
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
