## `epub_enricher/gui/` Module GUI 🖼️

Ce module contient l'implémentation de l'interface utilisateur graphique (GUI) de l'outil **EPUB Enricher** en utilisant la bibliothèque standard **Tkinter** de Python.

Cette interface permet aux utilisateurs de **scanner** un dossier contenant des fichiers EPUB, de **visualiser** les métadonnées originales, de **récupérer des suggestions** de métadonnées (titre, auteurs, couverture, etc.) via l'API OpenLibrary, de **comparer** les informations, et d'**appliquer** les enrichissements choisis.

---

### Structure des Fichiers

| Fichier                   | Description                                                                                                                       |
| :------------------------ | :-------------------------------------------------------------------------------------------------------------------------------- |
| **`__init__.py`**         | Marque ce répertoire comme un paquet Python.                                                                                      |
| **`main_window.py`**      | Contient la classe principale **`EnricherGUI`**, l'orchestrateur de l'interface utilisateur.                                      |
| **`comparison_frame.py`** | **Nouveau** : Implémente le panneau de comparaison visuelle (Original vs. Suggestion) des métadonnées et des couvertures.         |
| **`editions_window.py`**  | **Nouveau** : Fenêtre modale pour afficher la liste des éditions alternatives trouvées sur OpenLibrary et permettre la sélection. |
| **`task_manager.py`**     | **Nouveau** : Gère l'exécution des tâches de fond (fetch de suggestions, application) dans des threads séparés.                   |
| **`helpers.py`**          | **Nouveau** : Contient des fonctions utilitaires, notamment pour la manipulation des modèles de données et l'export CSV.          |

---

### `main_window.py`: Fonctionnalités Clés (Orchestrateur)

La classe `EnricherGUI` est responsable de la gestion de l'ensemble de l'expérience utilisateur et délègue les logiques complexes :

#### 1. Gestion des EPUBs et Affichage (Treeview)

-   **Sélection et Scan** : Les méthodes `select_folder` et `scan_folder` permettent de charger une liste de fichiers EPUB et d'en extraire les métadonnées originales.
-   **`refresh_tree`** : Met à jour la liste principale (`ttk.Treeview`) affichant l'état de chaque fichier (nom, titre, auteurs, statut, **score de qualité**).

#### 2. Zone de Comparaison et Détail (via `ComparisonFrame`)

-   **`on_select`** : Charge les métadonnées **originales** et **suggérées** de l'EPUB sélectionné dans le `ComparisonFrame`.
-   **`choose_field`** et **`choose_cover`** : Permettent de copier la valeur originale vers le champ suggéré final.

#### 3. Récupération et Application des Suggestions (via `task_manager.py`)

-   **`fetch_suggestions_for_selected`** : **Délègue** la recherche de suggestions à `task_manager.start_fetch_task`.
    -   Les éditions alternatives trouvées sont affichées via **`launch_editions_window`**, qui utilise `EditionsWindow`.
-   **`accept_selected`** / **`reject_selected`** : Marque l'état pour application ou réinitialise les suggestions (**via `helpers.py`**).
-   **`apply_accepted`** : **Délègue** le processus de modification des fichiers à `task_manager.start_apply_task`.

#### 4. Gestion de la Vue et Export

-   **`get_cover_photo`** : Gère un cache pour les objets images de Tkinter/Pillow pour optimiser l'affichage.
-   **`export_csv`** : **Délègue** l'exportation des données dans un fichier CSV (**via `helpers.py`**).

---

### Nouveaux Composants Dédiés

#### `comparison_frame.py`: Panneau de Détail

Ce composant `ttk.LabelFrame` :

-   Affiche les **métadonnées** côte à côte (Original/Final).
-   Intègre les `tk.Canvas` pour afficher les miniatures de **couverture**.
-   Inclut la méthode **`draw_cover`** pour le rendu des images `bytes` en utilisant PIL/Pillow.
-   Met à jour la couleur de fond des champs pour signaler les différences.

#### `editions_window.py`: Sélecteur d'Éditions

Ce `tk.Toplevel` modal :

-   Affiche les éditions alternatives trouvées (titre, auteurs, ISBN, éditeur, etc.) dans un `ttk.Treeview`.
-   Permet à l'utilisateur de sélectionner une édition, dont les données sont ensuite appliquées au modèle de métadonnées (`_on_edition_selected` dans `main_window.py`).

#### `task_manager.py`: Gestionnaire de Threads

Ce module sépare la logique bloquante de l'interface utilisateur :

-   **`start_fetch_task`** : Lance le _worker_ qui interroge OpenLibrary et télécharge les couvertures.
-   **`start_apply_task`** : Lance le _worker_ qui modifie les fichiers EPUB sur le disque avec les métadonnées acceptées.

#### `helpers.py`: Fonctions Utilitaires

Ce module fournit des fonctions réutilisables :

-   **`calculate_metadata_quality`** : Calcule un score de remplissage des métadonnées (affiché dans le Treeview).
-   **`apply_suggestions_to_model`** : Copie les champs `suggested_` vers les champs `original_` après acceptation.
-   **`reset_suggestions_on_model`** : Réinitialise les champs `suggested_` et le statut.
-   **`export_to_csv`** : Gère l'écriture de l'état complet des métadonnées dans un fichier CSV.
