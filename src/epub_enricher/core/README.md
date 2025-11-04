# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (**OpenLibrary**, **Google Books**, **Wikipedia**) et de l'application de ces suggestions aux fichiers EPUB.

---

## 📂 Structure du Module

Le dossier `core` est composé des fichiers suivants :

| Fichier               | Description Principale                                                                                                                                                                                            |
| :-------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models.py`           | Définit le modèle de données `EpubMeta` utilisé pour gérer les métadonnées (**originales** et **suggérées**). Le modèle a été simplifié pour retirer les champs d'analyse de contenu interne.                     |
| `epub_processor.py`   | Contient les fonctions de lecture, d'écriture, de **sauvegarde horodatée**, de mise à jour physique et de **renommage** des fichiers EPUB.                                                                        |
| `external_apis.py`    | Intègre les APIs externes (Google Books, Wikipedia, OpenLibrary) pour récupérer le genre et le résumé. **Contient désormais les utilitaires de nettoyage HTML et de classification de genre basés sur le texte.** |
| `metadata_fetcher.py` | Implémente la logique de recherche complexe sur **OpenLibrary** (par ISBN et par titre/auteur) et gère l'infrastructure HTTP résiliente avec **backoff et retry**.                                                |

---

## 🔬 Détails du Module

### 1. Modèle de Données (`models.py`)

`models.py` définit la classe `EpubMeta` qui centralise toutes les informations sur un fichier :

-   Les champs **originaux** lus dans l'EPUB (titre, auteur, ISBN, etc.).
-   Les champs **suggérés** (obtenus à partir des sources externes), destinés à être appliqués à l'EPUB.
-   Les champs de **statut** (`processed`, `accepted`, `note`) pour suivre le flux de travail.

### 2. Gestion des Fichiers EPUB (`epub_processor.py`)

Ce module gère le cycle de vie de l'EPUB :

-   **Lecture et Écriture** : Fonctions sécurisées pour lire (`safe_read_epub`) et reconstruire un EPUB (mode _rebuild_ si nécessaire).
-   **Sauvegarde** : Création d'une copie horodatée (`backup_file`) avant toute modification.
-   **Extraction de Métadonnées** : Extraction des métadonnées OPF standard (titre, auteur, ISBN, langue) et de la couverture.
-   **Renommage** : Logique de renommage avancée basée sur les métadonnées suggérées/originales (`[Année] - Auteurs - Titre.epub`).

### 3. Recherche de Métadonnées Externes et Utilitaires (`external_apis.py` & `metadata_fetcher.py`)

Ce module gère l'interrogation d'APIs externes pour enrichir les métadonnées et inclut des fonctions utilitaires de texte.

#### `metadata_fetcher.py`

-   **Infrastructure HTTP Résiliente** : Le décorateur `@retry_backoff` met en œuvre une stratégie de **réessai exponentiel avec _jitter_** pour gérer les échecs réseau et assurer la fiabilité des appels externes.
-   **Recherche OpenLibrary** : Recherche complète (`query_openlibrary_full`) combinant ISBN et titre/auteur pour regrouper les éditions d'une œuvre.
-   **Cache de Couverture** : Fonctionnalité pour télécharger et mettre en cache les images de couverture.

#### `external_apis.py`

-   **Aggregator** : La fonction centrale (`fetch_genre_and_summary_from_sources`) interroge et agrège les résultats de plusieurs APIs (Google Books, Wikipedia, OpenLibrary) pour fournir le meilleur **Genre** et **Résumé** suggérés.
-   **Mappage et Classification** : Fonctions de mappage des catégories/sujets externes vers un genre standard, ainsi que la fonction de **classification de genre par mots-clés** et le **nettoyage de texte HTML** (déplacées depuis l'ancien module d'analyse de contenu).
