# epub_enricher/src/epub_enricher/gui/comparison_frame.py
"""
Composant GUI pour la zone de comparaison et de sélection des métadonnées.
"""

import logging
import tkinter as tk
from io import BytesIO
from tkinter import ttk
from typing import TYPE_CHECKING, Dict

# Importations pour le dessin de la couverture
from PIL import Image, ImageTk

from ..config import GUI_COVER_SIZE

if TYPE_CHECKING:
    from .main_window import EnricherGUI  # Importation pour le type hinting

logger = logging.getLogger(__name__)


class ComparisonFrame(ttk.LabelFrame):
    """
    Frame contenant les vues "Original", "Final" et les couvertures
    pour la comparaison des métadonnées.
    """

    def __init__(self, master, main_controller: "EnricherGUI", **kwargs):
        super().__init__(master, text="Comparaison et Sélection", **kwargs)
        self.main_controller = main_controller  # Référence vers la fenêtre principale

        self.detail_vars: Dict[str, Dict[str, tk.StringVar]] = {}
        self.detail_entries: Dict[str, Dict[str, ttk.Entry | tk.Text]] = {}

        self.create_comparison_widgets()

    def create_comparison_widgets(self):
        # Configuration des colonnes pour équilibrer
        self.columnconfigure(1, weight=1)  # Champ
        self.columnconfigure(2, weight=2)  # Valeur originale
        self.columnconfigure(3, weight=1)  # Bouton utiliser
        self.columnconfigure(4, weight=2)  # Valeur finale

        # --- Covers : fixées sur la gauche et la droite ---
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

        # Labels pour les couvertures
        ttk.Label(self, text="Couverture originale", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, padx=6, pady=3, sticky="w"
        )
        ttk.Label(self, text="Couverture suggérée", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=5, padx=6, pady=3, sticky="w"
        )

        # --- En-têtes de colonnes ---
        ttk.Label(self, text="Champ", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=1, padx=5, pady=3, sticky="w"
        )
        ttk.Label(self, text="Original", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=2, padx=5, pady=3, sticky="w"
        )
        ttk.Label(self, text="Valeur à appliquer", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=4, padx=5, pady=3, sticky="w"
        )

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
            ttk.Label(self, text=field_label).grid(row=i, column=1, padx=5, pady=5, sticky="w")

            self.detail_vars[field] = {"orig": tk.StringVar(), "final": tk.StringVar()}
            self.detail_entries[field] = {}

            # Widget spécial pour le résumé (zone de texte)
            if field == "summary":
                orig_text = tk.Text(self, height=3, width=30, state="disabled", wrap=tk.WORD)
                orig_text.grid(row=i, column=2, sticky="ew", padx=5)
                self.detail_entries[field]["orig"] = orig_text

                final_text = tk.Text(self, height=3, width=30, wrap=tk.WORD)
                final_text.grid(row=i, column=4, sticky="ew", padx=5)
                self.detail_entries[field]["final"] = final_text
            else:
                orig_entry = ttk.Entry(
                    self, textvariable=self.detail_vars[field]["orig"], state="readonly"
                )
                orig_entry.grid(row=i, column=2, sticky="ew", padx=5)
                self.detail_entries[field]["orig"] = orig_entry

                final_entry = ttk.Entry(self, textvariable=self.detail_vars[field]["final"])
                final_entry.grid(row=i, column=4, sticky="ew", padx=5)
                self.detail_entries[field]["final"] = final_entry

            # Bouton utiliser (appelle une méthode du contrôleur principal)
            use_btn = ttk.Button(
                self,
                text="→",
                width=4,
                command=lambda f=field: self.main_controller.choose_field(f, "orig"),
            )
            use_btn.grid(row=i, column=3, padx=2, pady=2)

        # --- Bouton utiliser cover ---
        ttk.Button(
            self,
            text="Utiliser cette couverture →",
            command=lambda: self.main_controller.choose_cover("orig"),
        ).grid(row=len(fields) + 2, column=0, columnspan=2, pady=(10, 6))

    # --- NOUVELLE MÉTHODE DE DESSIN ---

    def draw_cover(self, canvas: tk.Canvas, data: bytes | None):
        """Dessine la couverture sur le canevas fourni (déplacé du contrôleur)."""
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
            # Utilisation de PIL pour charger et redimensionner l'image
            pil = Image.open(BytesIO(data))
            original_size = pil.size
            # Utilisation de LANCZOS pour une meilleure qualité
            pil.thumbnail((w, h), Image.Resampling.LANCZOS)

            # Conversion en PhotoImage de Tkinter
            img = ImageTk.PhotoImage(pil)

            # Garder une référence sur le canevas pour éviter le garbage collector !
            canvas.image = img
            canvas.create_image(w // 2, h // 2, image=img)

            # Ajout d'informations de taille
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

            # Indication de qualité (exemple)
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

    # --- FIN NOUVELLE MÉTHODE DE DESSIN ---

    def load_meta(self, meta):
        """Charge les données d'un objet EpubMeta dans les champs de comparaison."""
        if meta is None:
            self.clear_details()
            return

        def format_list(items) -> str:
            return ", ".join(items) if items else ""

        # Champs de base
        self.detail_vars["title"]["orig"].set(meta.original_title or "")
        self.detail_vars["authors"]["orig"].set(format_list(meta.original_authors))
        self.detail_vars["publisher"]["orig"].set(meta.original_publisher or "")
        self.detail_vars["publication_date"]["orig"].set(meta.original_publication_date or "")
        self.detail_vars["isbn"]["orig"].set(meta.original_isbn or "")
        self.detail_vars["language"]["orig"].set(meta.original_language or "")
        self.detail_vars["tags"]["orig"].set(format_list(meta.original_tags))
        self.detail_vars["genre"]["orig"].set(meta.content_genre or "")

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
        orig_text = self.detail_entries["summary"]["orig"]
        orig_text.config(state="normal")
        orig_text.delete(1.0, tk.END)
        orig_text.insert(1.0, meta.content_summary or "")
        orig_text.config(state="disabled")

        final_text = self.detail_entries["summary"]["final"]
        final_text.delete(1.0, tk.END)
        final_text.insert(1.0, meta.suggested_summary or "")

        # Mise à jour des couvertures (Appel de la méthode interne draw_cover)
        self.draw_cover(self.cover_orig_canvas, meta.original_cover_data)  # CORRIGÉ
        self.draw_cover(self.cover_final_canvas, meta.suggested_cover_data)  # CORRIGÉ

        self.update_comparison_colors()

    def clear_details(self):
        """Vide les champs de la vue détaillée et les couvertures."""
        for field_vars in self.detail_vars.values():
            field_vars["orig"].set("")
            field_vars["final"].set("")

        # Vider les champs 'summary'
        self.detail_entries["summary"]["orig"].config(state="normal")
        self.detail_entries["summary"]["orig"].delete(1.0, tk.END)
        self.detail_entries["summary"]["orig"].config(state="disabled")
        self.detail_entries["summary"]["final"].delete(1.0, tk.END)

        self.update_comparison_colors()

        # Nettoyer les canvases de couverture (Appel de la méthode interne draw_cover)
        self.draw_cover(self.cover_orig_canvas, None)  # CORRIGÉ
        self.draw_cover(self.cover_final_canvas, None)  # CORRIGÉ

    def update_comparison_colors(self):
        """Met à jour les couleurs de fond des champs de comparaison."""
        style = ttk.Style()
        style.configure("OrigDiff.TEntry", fieldbackground="#FFDDDD")
        style.configure("FinalDiff.TEntry", fieldbackground="#DDFFDD")

        TEXT_ORIG_DIFF_BG = "#FFDDDD"
        TEXT_FINAL_DIFF_BG = "#DDFFDD"
        TEXT_DEFAULT_BG = "white"

        for field, vars_dict in self.detail_vars.items():
            orig_val = vars_dict["orig"].get()
            final_val = vars_dict["final"].get()

            orig_entry = self.detail_entries[field]["orig"]
            final_entry = self.detail_entries[field]["final"]

            is_text_widget = isinstance(orig_entry, tk.Text)

            if final_val and orig_val != final_val:
                if is_text_widget:
                    orig_entry.configure(background=TEXT_ORIG_DIFF_BG)
                    final_entry.configure(background=TEXT_FINAL_DIFF_BG)
                else:
                    orig_entry.configure(style="OrigDiff.TEntry")
                    final_entry.configure(style="FinalDiff.TEntry")
            else:
                if is_text_widget:
                    # Assurez-vous que l'état normal est rétabli pour les Text widgets
                    orig_entry.configure(background=TEXT_DEFAULT_BG)
                    final_entry.configure(background=TEXT_DEFAULT_BG)
                else:
                    orig_entry.configure(style="TEntry")
                    final_entry.configure(style="TEntry")
