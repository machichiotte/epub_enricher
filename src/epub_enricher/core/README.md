# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (**OpenLibrary**, **Google Books**, **Wikipedia**) et de l'application de ces suggestions aux fichiers EPUB.

---

## 📂 Structure du Module

Le dossier `core` est composé des fichiers suivants :

| Fichier               | Description Principale                                                                                                           |
| :-------------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| `models.py`           | Définit le modèle de données `EpubMeta` (inchangé).                                                                              |
| `file_utils.py`       | Gère les opérations sur le **système de fichiers** : trouver les EPUBs, **sauvegarde horodatée** et **renommage** de fichiers.   |
| `epub_metadata.py`    | Gère la **logique EPUB** : lecture, écriture, extraction et mise à jour des _métadonnées_ (mode _rebuild_).                      |
| `external_apis.py`    | Intègre les APIs externes (Google Books, Wikipedia, OpenLibrary) et contient les utilitaires de nettoyage HTML/texte (inchangé). |
| `metadata_fetcher.py` | Implémente la logique de recherche complexe (OpenLibrary) et l'infrastructure HTTP résiliente (inchangé).                        |

---

## 🔬 Détails du Module

### 1. Modèle de Données (`models.py`)

`models.py` définit la classe `EpubMeta` qui centralise toutes les informations sur un fichier :

-   Les champs **originaux** lus dans l'EPUB (titre, auteur, ISBN, etc.).
-   Les champs **suggérés** (obtenus à partir des sources externes), destinés à être appliqués à l'EPUB.
-   Les champs de **statut** (`processed`, `accepted`, `note`) pour suivre le flux de travail.

### 2. Gestion des Fichiers et Métadonnées (`file_utils.py` & `epub_metadata.py`)

L'ancien fichier `epub_processor.py` a été divisé en two modules pour une meilleure **séparation des responsabilités** :

-   **`epub_metadata.py`** : Gère le cycle de vie _interne_ de l'EPUB.

    -   **Lecture/Écriture** : Fonctions sécurisées pour lire (`safe_read_epub`) et reconstruire un EPUB (`update_epub_with_metadata`) en mode _rebuild_ pour nettoyer les métadonnées corrompues.
    -   **Extraction de Métadonnées** : Extraction des métadonnées OPF standard (titre, auteur, ISBN) et de la couverture.

-   **`file_utils.py`** : Gère les interactions avec le _système de fichiers_.
    -   **Recherche** : `find_epubs_in_folder` pour trouver les fichiers.
    -   **Sauvegarde** : Création d'une copie horodatée (`backup_file`) avant toute modification.
    -   **Renommage** : Logique de renommage avancée (`rename_epub_file`) basée sur les métadonnées (`[Année] - Auteurs - Titre.epub`).

### 3. Recherche de Métadonnées Externes et Utilitaires (`external_apis.py` & `metadata_fetcher.py`)

Ce module gère l'interrogation d'APIs externes pour enrichir les métadonnées et inclut des fonctions utilitaires de texte.

#### `metadata_fetcher.py`

-   **Infrastructure HTTP Résiliente** : Le décorateur `@retry_backoff` met en œuvre une stratégie de **réessai exponentiel avec _jitter_** pour gérer les échecs réseau et assurer la fiabilité des appels externes.
-   **Recherche OpenLibrary** : Recherche complète (`query_openlibrary_full`) combinant ISBN et titre/auteur pour regrouper les éditions d'une œuvre.
-   **Cache de Couverture** : Fonctionnalité pour télécharger et mettre en cache les images de couverture.

#### `external_apis.py`

-   **Aggregator** : La fonction centrale (`fetch_genre_and_summary_from_sources`) interroge et agrège les résultats de plusieurs APIs (Google Books, Wikipedia, OpenLibrary) pour fournir le meilleur **Genre** et **Résumé** suggérés.
-   **Mappage et Classification** : Fonctions de mappage des catégories/sujets externes vers un genre standard, ainsi que la fonction de **classification de genre par mots-clés** et le **nettoyage de texte HTML** (déplacées depuis l'ancien module d'analyse de contenu).
