# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (**OpenLibrary**, **Google Books**, **Wikipedia**) et de l'application de ces suggestions aux fichiers EPUB.

## ✨ Fonctionnalités Clés

-   **Reconstruction (Rebuild) :** Réécrit les fichiers EPUB en profondeur pour nettoyer les métadonnées corrompues ou invalides, assurant une compatibilité maximale.
-   **Agrégation Multi-Source :** Combine intelligemment les données d'OpenLibrary, Google Books et Wikipedia pour obtenir le meilleur résumé et la meilleure couverture.
-   **Extraction Intelligente :** Utilise plusieurs heuristiques pour trouver les métadonnées (ISBN, couverture, langue) même lorsqu'elles sont absentes ou mal formatées dans l'OPF.
-   **Réseau Résilient :** Implémente un mécanisme de **réessai automatique** (`@retry_backoff`) avec _exponential backoff_ et _jitter_ pour tous les appels API, garantissant la stabilité face aux échecs réseau.
-   **Renommage Standardisé :** Renomme les fichiers traités selon un format propre et configurable (ex: `[Année] - Auteur - Titre.epub`).
-   **Mise en Cache :** Possède un cache local pour les couvertures téléchargées, limitant les appels réseau redondants.
-   **Classification de Contenu :** Analyse le texte des résumés pour suggérer un genre (ex: "Science-Fiction", "Mystère") lorsque les tags externes sont absents.

## 🚀 Flux de Travail (Workflow)

Le processus de traitement d'un livre suit ces étapes principales :

1.  **Découverte :** `file_utils.py` scanne un dossier pour trouver tous les fichiers `.epub`.
2.  **Extraction :** `epub_metadata.py` lit chaque EPUB (`safe_read_epub`) et extrait toutes les métadonnées originales (`extract_metadata`).
3.  **Centralisation :** Un objet `EpubMeta` (`models.py`) est créé pour stocker l'état du livre (chemins, données originales).
4.  **Enrichissement :** `external_apis.py` orchestre les appels (`fetch_genre_and_summary_from_sources`) aux différentes APIs (OpenLibrary, Google Books, Wikipedia) en utilisant le titre, l'auteur ou l'ISBN.
5.  **Mise à jour du Modèle :** Les résultats (résumé, genre, couverture, etc.) sont stockés dans les champs `suggested_...` de l'objet `EpubMeta`.
6.  **Application (si acceptée par l'utilisateur) :**
    -   `file_utils.py` crée une sauvegarde de l'original (`backup_file`).
    -   `epub_metadata.py` reconstruit l'EPUB avec les nouvelles métadonnées (`update_epub_with_metadata`).
    -   `file_utils.py` renomme le fichier final (`rename_epub_file`).

---

## 📂 Architecture des Fichiers

Le dossier `core` est composé des fichiers suivants, chacun ayant une responsabilité claire :

| Fichier               | Rôle Principal                                                                                   |
| :-------------------- | :----------------------------------------------------------------------------------------------- |
| `models.py`           | Définit le modèle de données central `EpubMeta` qui suit l'état de chaque livre.                 |
| `file_utils.py`       | Gère les interactions avec le **système de fichiers** : découverte, sauvegarde et renommage.     |
| `epub_metadata.py`    | Gère la **logique EPUB** : lecture sécurisée, extraction de métadonnées et écriture (rebuild).   |
| `external_apis.py`    | **Orchestrateur** des APIs : agrège les résultats de Google, Wikipedia et OpenLibrary.           |
| `metadata_fetcher.py` | Logique de recherche **avancée** pour OpenLibrary et gestion du cache de couverture.             |
| `network_utils.py`    | Couche réseau **résiliente** : `http_get`, `http_download_bytes` et décorateur `@retry_backoff`. |
| `text_utils.py`       | **Utilitaires texte** : nettoyage HTML/texte et classification de genre par mots-clés.           |

---

## 🔬 Logique Détaillée par Composant

### 1. Données et Fichiers (`models.py`, `file_utils.py`)

-   **`models.py`** : Le cœur du système. `EpubMeta` est une `dataclass` qui sépare clairement les métadonnées `original_` (lues depuis le fichier) des `suggested_` (récupérées des APIs).
-   **`file_utils.py`** :
    -   `find_epubs_in_folder` : Recherche récursive des fichiers supportés.
    -   `backup_file` : Crée une copie horodatée dans le dossier `BACKUP_DIR` avant toute modification.
    -   `rename_epub_file` : Construit un nom de fichier standardisé à partir des métadonnées finales, en gérant les collisions (`_resolve_filename_collision`).

### 2. Interaction EPUB (`epub_metadata.py`)

Ce module est crucial car il gère la manipulation binaire des fichiers EPUB.

-   **Extraction (`extract_metadata`)** : Utilise `ebooklib` pour lire les métadonnées. Il implémente plusieurs **stratégies de fallback** :
    -   **Couverture :** Tente 3 méthodes (`ITEM_COVER`, métadonnées `OPF`, puis "brute-force" sur les images).
    -   **ISBN :** Cherche dans les identifiants DC, puis scanne le contenu texte des premières pages si absent (`_find_isbn_in_text`).
    -   **Langue :** Lit le champ DC, puis utilise `langdetect` sur le contenu texte (`_detect_language_from_text`).
-   **Écriture (`update_epub_with_metadata`)** : C'est la fonction la plus sensible. Elle **reconstruit entièrement l'EPUB** au lieu de simplement modifier l'OPF.
    > Ce mode "rebuild" est essentiel car de nombreux EPUBs ont des métadonnées corrompues ou dupliquées. La reconstruction garantit un fichier propre. Elle copie tous les items (HTML, CSS, images) sauf l'ancienne couverture (si une nouvelle est fournie) et génère de nouveaux fichiers de navigation (NCX/NAV).

### 3. Sources de Données Externes (`external_apis.py`, `metadata_fetcher.py`)

-   **`external_apis.py`** : Sert de point d'entrée unique pour l'enrichissement.
    -   `fetch_genre_and_summary_from_sources` : La fonction principale qui interroge toutes les sources (OpenLibrary, Google Books, Wikipedia) et agrège les résultats.
    -   `_aggregate_genre` : Logique de priorité pour définir le genre (Tags OpenLibrary > Tags Google > Analyse de texte du résumé).
    -   Contient également les appels simples à `query_google_books` et `query_wikipedia_summary`.
-   **`metadata_fetcher.py`** : Gère la logique complexe spécifique à OpenLibrary.
    -   `query_openlibrary_full` : Effectue une recherche en plusieurs étapes (par ISBN ou Titre/Auteur) pour trouver la "Work" (œuvre) et l'"Edition" afin de récupérer les métadonnées les plus complètes.
    -   `download_cover` : Gère le téléchargement et la mise en cache (dans `COVER_CACHE_DIR`) des images de couverture.

### 4. Utilitaires de Support (`network_utils.py`, `text_utils.py`)

-   **`network_utils.py`** : Assure la robustesse des appels externes.
    -   `@retry_backoff` : Un décorateur qui encapsule les requêtes HTTP. En cas d'échec (ex: erreur 503, timeout), il attend de manière exponentielle (avec _jitter_) avant de réessayer, évitant ainsi de surcharger l'API.
    -   `http_get` / `http_download_bytes` : Fonctions de base pour les requêtes, utilisant le décorateur de réessai.
-   **`text_utils.py`** : Fournit des outils de nettoyage et d'analyse.
    -   `clean_html_text` : Utilise des expressions régulières pour convertir le HTML (souvent présent dans les résumés d'API) en texte brut.
    -   `classify_genre_from_text` : Fonction de _fallback_ qui analyse le résumé pour y trouver des mots-clés (ex: "espace", "magie", "détective") afin de deviner le genre.
