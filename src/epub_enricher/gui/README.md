## `epub_enricher/gui/` Module GUI 🖼️

Ce module contient l'implémentation de l'interface utilisateur graphique (GUI) de l'outil **EPUB Enricher** en utilisant la bibliothèque standard **Tkinter** de Python.

Cette interface permet aux utilisateurs de **scanner** un dossier contenant des fichiers EPUB, de **visualiser** les métadonnées originales, de **récupérer des suggestions** de métadonnées (titre, auteurs, couverture, etc.) via l'API OpenLibrary, de **comparer** les informations, et d'**appliquer** les enrichissements choisis.

---

### Structure des Fichiers

| Fichier              | Description                                                                                  |
| :------------------- | :------------------------------------------------------------------------------------------- |
| **`__init__.py`**    | Marque ce répertoire comme un paquet Python.                                                 |
| **`main_window.py`** | Contient la classe principale **`EnricherGUI`**, qui est le cœur de l'interface utilisateur. |

---

### `main_window.py`: Fonctionnalités Clés

La classe `EnricherGUI` est responsable de la gestion de l'ensemble de l'expérience utilisateur:

#### 1. Gestion des EPUBs et Affichage (Treeview)

-   **Sélection et Scan** : Les méthodes `select_folder` et `scan_folder` permettent de charger une liste de fichiers EPUB et d'en extraire les métadonnées originales, y compris les données binaires de la couverture (`original_cover_data`).
-   **`refresh_tree`** : Met à jour la liste principale (`ttk.Treeview`) affichant l'état de chaque fichier (nom, titre, auteurs, statut: _idle_, _processed_, _accepted_).

#### 2. Zone de Comparaison et Détail

-   **`on_select`** : Charge les métadonnées **originales** et **suggérées** de l'EPUB sélectionné dans des champs de saisie dédiés.
-   **`update_comparison_colors`** : Met en surbrillance (en rouge/vert) les champs où la valeur suggérée diffère de la valeur originale.
-   **`choose_field`** et **`choose_cover`** : Permettent de basculer facilement entre la valeur originale et la valeur suggérée (en copiant l'original vers le champ final) pour la couverture ou tout autre champ de métadonnée.

#### 3. Récupération et Application des Suggestions

-   **`fetch_suggestions_for_selected`** : Lance une opération dans un thread séparé (`_fetch_thread`) pour interroger OpenLibrary et remplir les champs de suggestions (`suggested_title`, `suggested_authors`, `suggested_cover_data`, etc.).
    -   Les éditions alternatives trouvées peuvent être affichées via **`show_related_editions`**.
-   **`accept_selected`** / **`reject_selected`** : Marque l'état pour indiquer si l'utilisateur souhaite appliquer ou ignorer les enrichissements.
-   **`apply_accepted`** : Lance le processus (`_apply_thread`) de modification réelle des fichiers EPUB sur disque en utilisant les métadonnées acceptées.

#### 4. Gestion Visuelle des Couvertures

-   **`get_cover_photo`** : Gère un cache (`cover_photo_cache`) pour les objets images de Tkinter/Pillow (`ImageTk.PhotoImage`) afin d'optimiser le rechargement des miniatures de couverture.
-   **`draw_cover`** : Affiche la miniature sur les `tk.Canvas` dédiés à la couverture originale et à la couverture finale/suggérée.

#### 5. Export

-   **`export_csv`** : Permet d'exporter l'état complet de tous les EPUBs (métadonnées originales et suggérées, statut, notes) dans un fichier CSV.
