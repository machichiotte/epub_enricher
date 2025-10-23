# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (comme OpenLibrary) et de l'application de ces suggestions aux fichiers EPUB.

---

## 📂 Structure du Module

Le dossier `core` est composé des fichiers suivants :

| Fichier               | Description Principale                                                                                                                                                          |
| :-------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `models.py`           | Définit le modèle de données `EpubMeta` utilisé pour gérer les métadonnées (originales et suggérées).                                                                           |
| `epub_processor.py`   | Contient les fonctions de lecture, d'écriture et de mise à jour des fichiers EPUB, ainsi que l'extraction des métadonnées existantes (titre, auteur, ISBN, langue, couverture). |
| `metadata_fetcher.py` | Contient la logique pour interroger les APIs externes (**OpenLibrary**) pour trouver des métadonnées enrichies et télécharger les images de couverture.                         |

---

## 📖 Fonctionnalités Clés

### 1. Modèle de Données (`models.py`)

Le modèle `EpubMeta` (basé sur `dataclass`) est le conteneur central pour l'état de l'EPUB. Il stocke :

-   Les **métadonnées originales** (lues depuis le fichier).
-   Les **métadonnées suggérées** (trouvées via des sources externes), destinées à être appliquées à l'EPUB.
-   Les champs de **statut** (`processed`, `accepted`, `note`) pour suivre le flux de travail.

### 2. Gestion des Fichiers EPUB (`epub_processor.py`)

Ce fichier gère les interactions directes avec les fichiers EPUB en utilisant la bibliothèque `ebooklib`.

-   **Extraction de Métadonnées** :
    -   Récupère le titre, les auteurs et la langue depuis l'EPUB.
    -   L'**ISBN** est recherché dans les identifiants et le contenu textuel, puis **normalisé**.
    -   L'image de **couverture** est extraite (via `ITEM_COVER` ou métadonnées OPF).
    -   La langue peut être **détectée** à partir du contenu si la métadonnée est manquante.
-   **Sauvegarde et Mise à Jour** :
    -   Une **sauvegarde** horodatée est créée avant toute modification.
    -   Les métadonnées suggérées (titre, auteurs, ISBN, langue) et l'image de couverture sont appliquées pour mettre à jour l'EPUB.
-   **Recherche de Fichiers** : La fonction `find_epubs_in_folder` permet de localiser tous les fichiers EPUB dans un répertoire et ses sous-répertoires.

### 3. Recherche de Métadonnées Externes (`metadata_fetcher.py`)

Ce module gère l'interrogation d'APIs externes, principalement **OpenLibrary**.

-   **Infrastructure HTTP Résiliente** : Les requêtes HTTP utilisent un décorateur `@retry_backoff` pour mettre en œuvre une stratégie de **réessai exponentiel avec _jitter_** pour gérer les échecs réseau.
-   **Recherche OpenLibrary** :
    -   **Recherche complète** (`query_openlibrary_full`) combine la recherche par ISBN et par titre/auteur.
    -   Récupération des **détails complets** d'une œuvre (`Work`) et d'une édition (`Edition`) pour obtenir la description, les dates, etc..
-   **Gestion des Couvertures** : `download_cover` télécharge les images de couverture et les stocke dans un **cache local** (nommé via un hachage SHA1 de l'URL) pour optimiser les accès répétés.
