# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (**OpenLibrary**) et de l'application de ces suggestions aux fichiers EPUB.

---

## 📂 Structure du Module

Le dossier `core` est composé des fichiers suivants :

| Fichier               | Description Principale                                                                                                                                                                                   |
| :-------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models.py`           | Définit le modèle de données `EpubMeta` utilisé pour gérer les métadonnées (**originales** et **suggérées**).                                                                                            |
| `epub_processor.py`   | Contient les fonctions de lecture, d'écriture, de **sauvegarde horodatée** et de mise à jour physique des fichiers EPUB.                                                                                 |
| `content_analyzer.py` | Gère l'analyse approfondie du contenu de l'EPUB pour l'extraction de l'ISBN à partir du texte, la détection de la langue manquante et l'extraction de l'image de couverture.                             |
| `external_apis.py`    | Fournit l'infrastructure HTTP résiliente (gestion des erreurs, **réessai exponentiel avec _jitter_**) et les clients de base pour interroger les services externes.                                      |
| `metadata_fetcher.py` | Orchestre la logique d'interrogation des APIs (principalement **OpenLibrary**) pour trouver des métadonnées enrichies (titre, auteur, description, dates, etc.) et télécharger les images de couverture. |

---

## 📖 Fonctionnalités Clés

### 1. Modèle de Données (`models.py`)

Le modèle `EpubMeta` (basé sur `dataclass`) est le conteneur central pour l'état de l'EPUB. Il stocke :

-   Les **métadonnées originales** (lues depuis le fichier).
-   Les **métadonnées suggérées** (trouvées via des sources externes), destinées à être appliquées à l'EPUB.
-   Les champs de **statut** (`processed`, `accepted`, `note`) pour suivre le flux de travail.

### 2. Gestion et Analyse des Fichiers EPUB (`epub_processor.py` & `content_analyzer.py`)

#### `epub_processor.py`

Ce fichier gère les interactions directes avec les fichiers EPUB en utilisant la bibliothèque `ebooklib`.

-   **Sauvegarde et Mise à Jour** : Une **sauvegarde** horodatée est créée avant toute modification. Les métadonnées suggérées et la nouvelle image de couverture sont appliquées pour mettre à jour l'EPUB.
-   **Recherche de Fichiers** : La fonction `find_epubs_in_folder` permet de localiser tous les fichiers EPUB dans un répertoire et ses sous-répertoires.

#### `content_analyzer.py`

Ce module se concentre sur l'extraction des informations non triviales :

-   **Extraction de Métadonnées Spécifiques** : L'**ISBN** est recherché dans les identifiants et le contenu textuel, puis **normalisé**.
-   **Détection et Extraction** : L'image de **couverture** est extraite (via `ITEM_COVER` ou métadonnées OPF). La langue peut être **détectée** à partir du contenu si la métadonnée est manquante.

### 3. Recherche de Métadonnées Externes (`external_apis.py` & `metadata_fetcher.py`)

Ce module gère l'interrogation d'APIs externes.

#### `external_apis.py`

-   **Infrastructure HTTP Résiliente** : Les requêtes HTTP utilisent un décorateur `@retry_backoff` pour mettre en œuvre une stratégie de **réessai exponentiel avec _jitter_** pour gérer les échecs réseau et assurer la fiabilité des appels externes.

#### `metadata_fetcher.py`

-   **Recherche OpenLibrary** :
    -   **Recherche complète** (`query_openlibrary_full`) combine la recherche par ISBN et par titre/auteur.
    -   Récupération des **détails complets** d'une œuvre (`Work`) et d'une édition (`Edition`) pour obtenir la description, les dates, etc.
-   **Gestion des Couvertures** : `download_cover` télécharge les images de couverture et les stocke dans un **cache local** (nommé via un hachage SHA1 de l'URL) pour optimiser les accès répétés.
