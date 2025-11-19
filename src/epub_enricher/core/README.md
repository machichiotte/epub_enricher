# 📚 EPUB Enricher - Module Cœur (`core`)

Ce module contient la **logique métier principale** du projet EPUB Enricher. Il est responsable de la lecture et de l'écriture des fichiers EPUB, de l'extraction des métadonnées existantes, de la recherche de métadonnées enrichies via des services externes (**OpenLibrary**, **Google Books**, **Wikipedia**) et de l'application de ces suggestions aux fichiers EPUB.

## 🏗️ Architecture (Post-Refactoring)

Le module core est désormais organisé en **sous-modules spécialisés** suivant les principes SOC/SOR :

```
core/
├── epub/                    # 📖 Manipulation EPUB
│   ├── reader.py           # Extraction métadonnées
│   ├── writer.py           # Écriture/rebuild
│   ├── cover_finder.py     # Recherche couverture (Strategy)
│   └── metadata_extractors.py  # Extracteurs avancés
├── enrichment/              # 🌐 APIs externes
│   ├── google_books.py     # Client Google Books
│   ├── wikipedia.py        # Client Wikipedia
│   ├── aggregator.py       # Orchestration multi-sources
│   └── genre_mapper.py     # Classification genres
├── enricher_service.py      # 🔧 Service Layer (orchestrateur)
├── openlibrary_client.py    # 📚 Client OpenLibrary
├── models.py                # 📊 EpubMeta dataclass
├── file_utils.py            # 📁 Gestion fichiers
├── network_utils.py         # 🌐 HTTP + retry pattern
└── text_utils.py            # 📝 Nettoyage texte
```

## ✨ Fonctionnalités Clés

-   **Reconstruction (Rebuild) :** Réécrit les fichiers EPUB en profondeur pour nettoyer les métadonnées corrompues ou invalides, assurant une compatibilité maximale.
-   **Agrégation Multi-Source :** Combine intelligemment les données d'OpenLibrary, Google Books et Wikipedia pour obtenir le meilleur résumé et la meilleure couverture.
-   **Extraction Intelligente :** Utilise plusieurs heuristiques pour trouver les métadonnées (ISBN, couverture, langue) même lorsqu'elles sont absentes ou mal formatées dans l'OPF.
-   **Réseau Résilient :** Implémente un mécanisme de **réessai automatique** (`@retry_backoff`) avec _exponential backoff_ et _jitter_ pour tous les appels API, garantissant la stabilité face aux échecs réseau.
-   **Service Layer :** `EnricherService` fournit une API réutilisable pour GUI et CLI, éliminant la duplication de code.
-   **Mise en Cache :** Possède un cache local pour les couvertures téléchargées, limitant les appels réseau redondants.
-   **Classification de Contenu :** Analyse le texte des résumés pour suggérer un genre (ex: \"Science-Fiction\", \"Mystère\") lorsque les tags externes sont absents.

## 🚀 Flux de Travail (Workflow)

Le processus de traitement d'un livre suit ces étapes principales :

### Via EnricherService (Recommandé)

```python
from epub_enricher.core.enricher_service import EnricherService

service = EnricherService()

# 1. Traiter un EPUB (extraction + enrichissement)
meta = service.process_epub("path/to/book.epub")

# 2. Appliquer les enrichissements
if meta.processed:
    success = service.apply_enrichment(meta)
    
# 3. Traiter un dossier complet
metas = service.process_folder("/path/to/folder", autosave=False)
```

### Flux Détaillé

1.  **Découverte :** `file_utils.py` scanne un dossier pour trouver tous les fichiers `.epub`.
2.  **Extraction :** `epub/reader.py` lit chaque EPUB et extrait toutes les métadonnées originales.
3.  **Centralisation :** Un objet `EpubMeta` (`models.py`) est créé pour stocker l'état du livre.
4.  **Enrichissement :** 
    - `openlibrary_client.py` recherche les éditions possibles
    - `enrichment/aggregator.py` orchestre les appels aux APIs (Google, Wikipedia)
    - `enrichment/genre_mapper.py` agrège les genres
5.  **Mise à jour du Modèle :** Les résultats sont stockés dans les champs `suggested_...` de `EpubMeta`.
6.  **Application (si acceptée) :**
    -   `file_utils.py` crée une sauvegarde de l'original.
    -   `epub/writer.py` reconstruit l'EPUB avec les nouvelles métadonnées.
    -   `file_utils.py` renomme le fichier final.

---

## 📂 Détail des Composants

### Sous-Modules

#### `epub/` - Manipulation EPUB
Voir [`epub/README.md`](epub/README.md) pour la documentation complète.
- **Responsabilité** : Tout ce qui touche aux fichiers EPUB
- **Pattern** : Strategy (recherche de couverture)

#### `enrichment/` - APIs Externes  
Voir [`enrichment/README.md`](enrichment/README.md) pour la documentation complète.
- **Responsabilité** : Récupération de métadonnées depuis sources externes
- **Pattern** : Facade + Aggregator

### Modules Principaux

| Fichier               | Rôle Principal                                                                                   |
| :-------------------- | :----------------------------------------------------------------------------------------------- |
| `models.py`           | Définit le modèle de données central `EpubMeta` qui suit l'état de chaque livre.                 |
| `enricher_service.py` | **Service Layer** : Orchestrateur du workflow complet, réutilisable par GUI et CLI.              |
| `openlibrary_client.py` | Client OpenLibrary : recherche avancée, gestion cache de couverture.                          |
| `file_utils.py`       | Gère les interactions avec le **système de fichiers** : découverte, sauvegarde et renommage.     |
| `network_utils.py`    | Couche réseau **résiliente** : `http_get`, `http_download_bytes` et décorateur `@retry_backoff`. |
| `text_utils.py`       | **Utilitaires texte** : nettoyage HTML/texte et classification de genre par mots-clés.           |

---

## 🔬 Logique Détaillée par Composant

### EnricherService - Service Layer

Le point d'entrée recommandé pour toute interaction avec le core :

```python
class EnricherService:
    def process_epub(self, epub_path: str) -> Optional[EpubMeta]
        """Extrait + enrichit les métadonnées d'un EPUB."""
        
    def apply_enrichment(self, meta: EpubMeta) -> bool
        """Applique les suggestions au fichier EPUB."""
        
    def process_folder(self, folder: str, autosave: bool) -> List[EpubMeta]
        """Traite un dossier complet."""
```

**Avantages** :
- Élimine duplication GUI/CLI
- API simple et testable
- Gestion d'erreurs centralisée

### Données et Fichiers (`models.py`, `file_utils.py`)

-   **`models.py`** : Le cœur du système. `EpubMeta` est une `dataclass` qui sépare clairement les métadonnées `original_` (lues depuis le fichier) des `suggested_` (récupérées des APIs).
-   **`file_utils.py`** :
    -   `find_epubs_in_folder` : Recherche récursive des fichiers supportés.
    -   `backup_file` : Crée une copie horodatée dans le dossier `BACKUP_DIR` avant toute modification.
    -   `rename_epub_file` : Construit un nom de fichier standardisé à partir des métadonnées finales.

### Utilitaires de Support (`network_utils.py`, `text_utils.py`)

-   **`network_utils.py`** : Assure la robustesse des appels externes.
    -   `@retry_backoff` : Un décorateur qui encapsule les requêtes HTTP. En cas d'échec (ex: erreur 503, timeout), il attend de manière exponentielle (avec _jitter_) avant de réessayer.
    -   `http_get` / `http_download_bytes` : Fonctions de base pour les requêtes HTTP.
-   **`text_utils.py`** : Fournit des outils de nettoyage et d'analyse.
    -   `clean_html_text` : Convertit HTML en texte brut.
    -   `classify_genre_from_text` : Fonction de _fallback_ qui analyse le résumé pour deviner le genre.

---

## 🔄 Migration depuis l'Ancienne Architecture

### Imports Dépréciés

⚠️ Les anciens modules `epub_metadata.py` et `external_apis.py` sont maintenant des **shims de compatibilité** :

```python
# ⚠️ DEPRECATED (fonctionne avec warning)
from epub_enricher.core.epub_metadata import extract_metadata
from epub_enricher.core.external_apis import fetch_genre_and_summary_from_sources

# ✅ NOUVEAU (recommandé)
from epub_enricher.core.epub import extract_metadata, update_epub_with_metadata
from epub_enricher.core.enrichment import fetch_enriched_metadata
from epub_enricher.core.enricher_service import EnricherService
```

### Utiliser EnricherService

Au lieu de manipuler directement les modules, utilisez le service :

```python
# ❌ Ancienne approche (complexe, dupliquée)
metadata = extract_metadata(path)
meta = EpubMeta(...)
suggestions = fetch_genre_and_summary_from_sources(...)
# ... logique de mapping manuelle

# ✅ Nouvelle approche (simple, réutilisable)
service = EnricherService()
meta = service.process_epub(path)  # Tout en un
```

---

## 📊 Métriques de Qualité

**Après refactorisation** :
- **Modules** : 2 monolithiques → 10 spécialisés (+400% modularité)
- **LOC par module** : ~200L max (vs 355L avant)
- **Tests** : 50 tests unitaires couvrant les composants critiques
- **Patterns** : Strategy, Service Layer, Facade, Retry

**Conformité SOC/SOR** : ✅ Excellente
- Chaque module a une responsabilité unique
- Séparation claire lecture/écriture, API/agrégation
- Infrastructure isolée (network, file, text utils)
