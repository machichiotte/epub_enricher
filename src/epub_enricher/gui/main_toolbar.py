# epub_enricher/src/epub_enricher/gui/main_toolbar.py
"""
Composant GUI pour la barre d'outils principale.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class MainToolbar(ttk.Frame):
    """Frame contenant les boutons d'action principaux."""

    def __init__(
        self,
        master,
        on_select_folder: Callable[[], None],
        on_fetch: Callable[[], None],
        on_apply: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        self.folder_var = tk.StringVar()

        ttk.Entry(self, textvariable=self.folder_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(self, text="Select & Scan Folder", command=on_select_folder).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(self, text="Fetch suggestions", command=on_fetch).pack(side=tk.LEFT, padx=4)
        ttk.Button(self, text="Apply Changes", command=on_apply).pack(side=tk.LEFT, padx=4)

    def set_folder_var(self, path: str):
        self.folder_var.set(path)
