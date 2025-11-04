# EPUB Enricher - Module GUI 🖼️

Ce module contient l'implémentation de l'interface utilisateur graphique (GUI) de l'outil **EPUB Enricher** en utilisant la bibliothèque standard **Tkinter** de Python.

Cette interface permet aux utilisateurs de **scanner** un dossier contenant des fichiers EPUB, de **visualiser** les métadonnées originales, de **récupérer des suggestions** d'éditions (via les modules Core), et d'**éditer** puis **appliquer** les enrichissements choisis.

---

### Structure des Fichiers dans `epub_enricher/gui/`

| Fichier                   | Description                                                                                                                    |
| :------------------------ | :----------------------------------------------------------------------------------------------------------------------------- |
| **`__init__.py`**         | Marque ce répertoire comme un paquet Python.                                                                                   |
| **`main_window.py`**      | Contient la classe principale **`EnricherGUI`**, l'orchestrateur de l'interface utilisateur et le gestionnaire des événements. |
| **`comparison_frame.py`** | **MISE À JOUR MAJEURE** : Panneau d'édition **ET** sélection des éditions alternatives (via Treeview).                         |
| ~~`editions_window.py`~~  | **(Obsolète/Supprimé)** La logique de sélection des éditions est désormais intégrée dans `comparison_frame.py`.                |
| **`task_manager.py`**     | Gère l'exécution des tâches de fond (fetch/apply) dans des threads séparés pour maintenir la réactivité de la GUI.             |
| **`helpers.py`**          | Fonctions utilitaires, notamment le calcul de score, l'export CSV, et les helpers pour la manipulation du modèle.              |

---

### Logique et Rôle des Composants Clés (Post-Refonte)

#### `main_window.py`: Contrôleur Principal

-   Orchestre l'affichage du Treeview des fichiers et du `ComparisonFrame`.
-   Contient les méthodes de navigation (sélection d'un fichier).
-   Gère les événements utilisateur pour déclencher les tâches de fond (`fetch`, `apply`, `export`).
-   **`export_csv`**: Déclenche l'export CSV via le module `helpers`.

#### `comparison_frame.py`: Panneau d'Édition et Sélection

Ce composant `ttk.LabelFrame` est central pour la phase d'édition :

-   Affiche les métadonnées côte à côte ("Original" en lecture seule, "Valeur à appliquer" en **lecture/écriture**).
-   Affiche les couvertures.
-   **Intégration du `Treeview` des éditions trouvées** : Affiche les `meta.found_editions` pour la sélection.
-   **`_on_edition_selected_from_tree`** : Méthode clé qui peuple les champs "Valeur à appliquer" (les `StringVar`s de la vue) avec les données de l'édition sélectionnée.
-   **`save_final_values_to_model`** : Méthode clé qui lit les `StringVar`s (édités manuellement ou peuplés par une sélection) et les sauvegarde dans les champs `suggested_...` de l'objet `EpubMeta` avant l'application.

#### `task_manager.py`: Gestionnaire de Threads

Ce module assure que les opérations longues (Fetch API, Application des changements) n'impactent pas l'interface graphique.

-   **`_fetch_worker`** : Récupère les données d'OpenLibrary et met à jour les champs `suggested_...` et `found_editions` du modèle.
-   **`_apply_worker`** : Exécute le processus de mise à jour du fichier EPUB (via les modules Core).
    -   **Mise à Jour du Modèle** : Après une application réussie, il appelle **`helpers.apply_suggestions_to_model(m)`** pour copier les valeurs `suggested_` vers `original_` (persistance des changements).
    -   Nettoie le modèle en appelant `helpers.reset_suggestions_on_model(m)`.

#### `helpers.py`: Fonctions Utilitaires

Contient des fonctions de manipulation de données ou d'export :

-   **`calculate_metadata_quality`**: Calcule un score de qualité pour les métadonnées.
-   **`export_meta_list_to_csv`**: Exporte l'état actuel de tous les fichiers (original et suggéré) dans un CSV.
-   **`apply_suggestions_to_model`**: **Nouvelle fonction** appelée par le `task_manager` pour copier les valeurs `suggested_` dans les champs `original_` après l'application.
-   **`reset_suggestions_on_model`**: Efface les champs `suggested_...` (titre, auteur, etc.) et réinitialise les indicateurs.
