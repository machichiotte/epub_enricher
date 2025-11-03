## `epub_enricher/gui/` Module GUI 🖼️

Ce module contient l'implémentation de l'interface utilisateur graphique (GUI) de l'outil **EPUB Enricher** en utilisant la bibliothèque standard **Tkinter** de Python.

Cette interface permet aux utilisateurs de **scanner** un dossier contenant des fichiers EPUB, de **visualiser** les métadonnées originales, de **récupérer des suggestions** d'éditions via l'API OpenLibrary, et d'**éditer** puis **appliquer** les enrichissements choisis.

---

### Structure des Fichiers

| Fichier                   | Description                                                                                                                |
| :------------------------ | :------------------------------------------------------------------------------------------------------------------------- |
| **`__init__.py`**         | Marque ce répertoire comme un paquet Python.                                                                               |
| **`main_window.py`**      | Contient la classe principale **`EnricherGUI`**, l'orchestrateur de l'interface utilisateur.                               |
| **`comparison_frame.py`** | Implémente le panneau d'édition (Original vs. Final) et la liste des éditions alternatives trouvées pour sélection.        |
| ~~`editions_window.py`~~  | (Obsolète) La logique est désormais intégrée dans `comparison_frame.py`.                                                   |
| **`task_manager.py`**     | Gère l'exécution des tâches de fond (fetch de suggestions, application) dans des threads séparés pour ne pas bloquer l'UI. |
| **`helpers.py`**          | Contient des fonctions utilitaires (calcul de score, manipulation du modèle de données, export CSV).                       |

---

### `main_window.py`: Fonctionnalités Clés (Orchestrateur)

La classe `EnricherGUI` gère l'expérience utilisateur et délègue les logiques complexes.

#### 1. Gestion des EPUBs et Affichage (Treeview)

-   **`select_and_scan_folder`** : Charge une liste de fichiers EPUB et extrait les métadonnées originales (`original_...`).
-   **`refresh_tree`** : Met à jour la liste principale (`ttk.Treeview`). La liste affiche l'état **final** (les valeurs `suggested_...` si elles existent, sinon les `original_...`).

#### 2. Zone d'Édition et de Sélection (via `ComparisonFrame`)

-   **`on_select`** : Charge les métadonnées dans le `ComparisonFrame`.
    -   La colonne **"Original"** (non éditable) affiche les données lues du fichier EPUB.
    -   La colonne **"Valeur à appliquer"** (éditable) affiche les données `suggested_...` du modèle.
-   **`save_final_values_to_model` (appelé par `on_select` ou `apply`)** : Sauvegarde toute modification manuelle dans la colonne "Valeur à appliquer" vers le modèle `EpubMeta` (`suggested_...`).

#### 3. Flux de Travail d'Enrichissement (Nouveau Workflow)

1.  **`fetch_suggestions_for_selected`** (via `task_manager.py`):

    -   Interroge OpenLibrary et d'autres APIs.
    -   Stocke **toutes** les éditions trouvées dans `meta.found_editions`.
    -   Pré-remplit les champs "Valeur à appliquer" (`suggested_...`) avec la "meilleure suggestion" trouvée.
    -   Le `ComparisonFrame` affiche la liste des `found_editions`.

2.  **Édition par l'utilisateur** (dans `comparison_frame.py`):

    -   L'utilisateur peut **éditer manuellement** n'importe quel champ "Valeur à appliquer".
    -   L'utilisateur peut cliquer sur une édition dans la liste pour **écraser** les champs "Valeur à appliquer" avec les données de cette édition.
    -   L'utilisateur peut utiliser le bouton `→` pour copier une valeur "Original" vers "Valeur à appliquer".

3.  **`apply_changes_to_selected`** (via `task_manager.py`):

    -   Bouton principal qui remplace "Accept" et "Apply".
    -   Prend les **fichiers sélectionnés** dans le Treeview.
    -   Lance une tâche de fond qui écrit les valeurs de "Valeur à appliquer" (`suggested_...`) directement dans les fichiers EPUB correspondants.
    -   Il n'y a **plus d'étape "d'acceptation"** intermédiaire.

4.  **`reset_selected`** (via `helpers.py`):
    -   Réinitialise l'état du fichier.
    -   Efface tous les champs `suggested_...`, la liste `found_editions` et réinitialise le statut à `idle`.

#### 4. Export

-   **`export_csv`** : Exporte l'état actuel (y compris les valeurs `suggested_...` non appliquées) dans un CSV.

---

### Composants Délégués

#### `comparison_frame.py`: Panneau d'Édition

Ce composant `ttk.LabelFrame` est central :

-   Affiche les métadonnées côte à côte ("Original" en lecture seule, "Valeur à appliquer" en **lecture/écriture**).
-   Affiche les couvertures.
-   **Nouveau** : Contient le `ttk.Treeview` affichant les `meta.found_editions`.
-   **`_on_edition_selected_from_tree`** : Méthode clé qui peuple les champs "Valeur à appliquer" (les `StringVar`s) lorsqu'une édition est sélectionnée.
-   **`save_final_values_to_model`** : Méthode clé qui lit les `StringVar`s (édités manuellement ou peuplés) et les sauvegarde dans l'objet `EpubMeta`.

#### `task_manager.py`: Gestionnaire de Threads

-   **`_fetch_worker`** : Récupère les données, pré-remplit `suggested_...` et remplit `found_editions`.
-   **`_apply_worker`** : Lit les `suggested_...` du modèle et les écrit dans le fichier EPUB.

#### `helpers.py`: Fonctions Utilitaires

-   **`apply_suggestions_to_model`** : Copie les champs `suggested_` (finaux) vers les champs `original_` (utilisé _après_ l'application au fichier).
-   **`reset_suggestions_on_model`** : Efface tous les champs `suggested_`, `found_editions` et le statut `processed`.
