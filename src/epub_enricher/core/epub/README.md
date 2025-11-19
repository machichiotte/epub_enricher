# Module EPUB - Manipulation de Fichiers EPUB

Ce sous-module gère **toute l'interaction avec les fichiers EPUB** : lecture, extraction de métadonnées, recherche de couverture, et écriture/reconstruction complète des fichiers.

## 📂 Structure

```
epub/
├── __init__.py              # Exports publics
├── reader.py                # Extraction de métadonnées
├── writer.py                # Écriture/rebuild EPUB
├── cover_finder.py          # Stratégies de recherche de couverture
└── metadata_extractors.py   # Extracteurs avancés (ISBN, langue)
```

## 🎯 Responsabilité

**Séparation stricte** :
- ✅ **Lecture** : `reader.py`
- ✅ **Écriture** : `writer.py`
- ✅ **Stratégies de couverture** : `cover_finder.py`
- ✅ **Extraction avancée** : `metadata_extractors.py`

## 📖 Modules

### `reader.py` - Extraction de Métadonnées

**Fonctions principales** :
- `extract_metadata(epub_path)` → Dict des métadonnées originales
- `safe_read_epub(epub_path)` → EpubBook ou None (lecture sécurisée)

**Stratégies d'extraction** :
- Lit les métadonnées Dublin Core (DC)
- Utilise `cover_finder` pour la couverture
- Utilise `metadata_extractors` pour ISBN et langue (si absents)

### `writer.py` - Écriture et Reconstruction

**Fonction principale** :
- `update_epub_with_metadata(epub_path, meta: EpubMeta)` → bool

**Mode Rebuild** :
> Reconstruit **entièrement** l'EPUB au lieu de modifier l'OPF.
> Garantit un fichier propre sans métadonnées corrompues ou dupliquées.

**Processus** :
1. Lit l'EPUB original avec `ebooklib`
2. Crée un nouveau `EpubBook`
3. Copie tous les items (HTML, CSS, images)
4. Applique les nouvelles métadonnées
5. Génère nouveaux NCX/NAV
6. Sauvegarde le fichier reconstruit

### `cover_finder.py` - Strategy Pattern

**Function principale** :
- `find_cover_data(book, epub_path)` → bytes ou None

**3 stratégies (dans l'ordre)** :
1. `_find_cover_by_type()` : Cherche ITEM_COVER
2. `_find_cover_by_opf()` : Lit métadonnées OPF
3. `_find_cover_by_bruteforce()` : Scan toutes les images

**Pattern Strategy** : Permet d'essayer plusieurs méthodes de fallback.

### `metadata_extractors.py` - Extracteurs Avancés

**Fonctions** :
- `detect_language_from_text(book)` : Utilise `langdetect` sur le contenu
- `find_isbn_in_text(book)` : Scanne le texte des premières pages

**Cas d'usage** : Quand les métadonnées Dublin Core sont absentes/incorrectes.

## 🔄 Flux d'Utilisation

```python
from epub_enricher.core.epub import extract_metadata, update_epub_with_metadata
from epub_enricher.core.models import EpubMeta

# 1. Extraction
metadata = extract_metadata("path/to/book.epub")
print(metadata["title"], metadata["authors"])

# 2. Création du modèle
meta = EpubMeta(
    path="path/to/book.epub",
    filename="book.epub",
    original_title=metadata["title"],
    # ... autres champs
    suggested_title="New Title",  # Mettre à jour après enrichissement
)

# 3. Application
success = update_epub_with_metadata("path/to/book.epub", meta)
```

## 🛡️ Gestion d'Erreurs

Toutes les fonctions gèrent les erreurs gracieusement :
- `safe_read_epub()` retourne `None` si fichier corrompu
- `extract_metadata()` retourne un dict avec toutes les clés (valeurs None si échec)
- `find_cover_data()` retourne `None` si aucune couverture trouvée

## ⚙️ Dépendances

- **ebooklib** : Manipulation EPUB
- **Pillow** : Traitement d'images (couvertures)
- **langdetect** : Détection de langue
- **isbnlib** : Validation ISBN

## 📝 Notes Techniques

**Pourquoi le mode Rebuild ?**
De nombreux EPUBs ont des métadonnées corrompues :
- Champs dupliqués
- Encodages invalides
- Tags non fermés

La reconstruction garantit un fichier propre et valide.

**Performance** :
- Lecture : ~100-200ms par fichier
- Écriture : ~300-500ms (rebuild complet)
