# Module Enrichment - Agrégation Multi-Sources

Ce sous-module gère **l'enrichissement de métadonnées** via des sources externes (Google Books, Wikipedia, OpenLibrary) et l'agrégation intelligente de leurs résultats.

## 📂 Structure

```
enrichment/
├── __init__.py           # Exports publics
├── google_books.py       # Client Google Books API
├── wikipedia.py          # Client Wikipedia API  
├── aggregator.py         # Orchestrateur multi-sources
└── genre_mapper.py       # Classification de genres
```

## 🎯 Responsabilité

**Séparation par source** :
- ✅ **Google Books** : `google_books.py`
- ✅ **Wikipedia** : `wikipedia.py`
- ✅ **Orchestration** : `aggregator.py`
- ✅ **Mapping de genres** : `genre_mapper.py`

**Avantages** :
- Ajout facile de nouvelles sources
- Tests isolés par API
- Maintenance simplifiée

## 📖 Modules

### `google_books.py` - Google Books API

**Fonction principale** :
- `query_google_books(title, isbn)` → Dict

**Retour** :
```python
{
    "summary": str,  # Description du livre
    "tags": List[str]  # Catégories/sujets
}
```

**Logique** :
- Priorité ISBN, sinon recherche par titre
- Parse les champs `volumeInfo.description` et `categories`
- Gestion d'erreurs gracieuse (retourne `{}`)

### `wikipedia.py` - Wikipedia API

**Fonction principale** :
- `query_wikipedia_summary(title)` → str ou None

**API utilisée** :
- REST API Wikipedia (pas besoin de clé)
- Endpoint : `https://fr.wikipedia.org/api/rest_v1/page/summary/{title}`

**Retour** :
- Résumé nettoyé (HTML → texte)
- `None` si page inexistante

### `aggregator.py` - Orchestrateur

**Fonction principale** :
- `fetch_enriched_metadata(title, authors, isbn)` → Dict complet

**Orchestration** :
```python
{
    "genre": str,           # Genre suggéré (agrégé)
    "summary": str,         # Meilleur résumé (priorité)
    "tags": List[str],      # Tags fusionnés
    "cover_data": bytes,    # Couverture (OpenLibrary)
    "ol_pub_date": str,     # Date de publication
    "ol_publisher": str,    # Éditeur
}
```

**Logique d'agrégation** :
1. Interroge en parallèle : OpenLibrary, Google Books, Wikipedia
2. **Résumé** : Priorité OL > Google > Wikipedia
3. **Genre** : Délègue à `genre_mapper.aggregate_genre()`
4. **Tags** : Fusion (dédoublonnage)
5. **Couverture** : OpenLibrary uniquement (meilleure qualité)

**Pattern** : Facade - masque la complexité multi-API.

### `genre_mapper.py` - Classification de Genres

**Fonctions principales** :
- `aggregate_genre(ol_tags, google_tags, summary)` → str ou None
- `map_tags_to_genre(tags)` → str ou None
- `map_openlibrary_subject_to_genre(subject)` → str ou None

**Logique de priorité** :
1. **Tags OpenLibrary** (plus fiables pour livres)
2. **Tags Google Books**
3. **Classification texte** du résumé (fallback)

**GENRE_MAPPING** :
Dictionnaire de mapping vers genres standards :
```python
{
    "Fiction": ["Fiction", "Literature", "Novel"],
    "Science-Fiction": ["Science Fiction", "Sci-Fi", ...],
    "Mystery": ["Mystery", "Crime", "Detective"],
    # ... 15 genres standards
}
```

## 🔄 Flux d'Utilisation

```python
from epub_enricher.core.enrichment import fetch_enriched_metadata

# Enrichissement complet
result = fetch_enriched_metadata(
    title="1984",
    authors=["George Orwell"],
    isbn="9780451524935"
)

print(result["genre"])    # "Fiction"
print(result["summary"])  # Long résumé du livre
print(len(result["tags"])) # Tags agrégés
```

## 🌐 Sources de Données

| Source | Utilisé pour | Qualité |
|--------|--------------|---------|
| **OpenLibrary** | Métadonnées, couverture, publisher | ⭐⭐⭐⭐⭐ |
| **Google Books** | Résumé, catégories | ⭐⭐⭐⭐ |
| **Wikipedia** | Résumé (fallback) | ⭐⭐⭐ |

**Note** : OpenLibrary est interrogé via `openlibrary_client.py` (module parent).

## 🛡️ Gestion d'Erreurs

- Chaque client retourne `{}` ou `None` en cas d'échec
- L'aggregator combine les résultats disponibles
- Résultat partiel possible (ex: genre sans résumé)

## ⚙️ Dépendances

- **requests** : Appels HTTP (via `network_utils`)
- **core.text_utils** : Nettoyage HTML, classification texte
- **core.openlibrary_client** : Client OpenLibrary

## 📊 Métriques

**Performance typique** (avec réseau) :
- Google Books : ~500ms
- Wikipedia : ~300ms
- OpenLibrary : ~1s (recherche complexe)
- **Total** : ~1.5-2s par livre

**Cache** :
- Couvertures mises en cache localement
- Pas de cache pour résumés/métadonnées (données changeantes)

## 🚀 Extension

**Ajouter une nouvelle source** :

1. Créer `enrichment/nouvelle_source.py`
2. Implémenter `query_nouvelle_source(title, isbn) -> Dict`
3. Ajouter l'appel dans `aggregator.fetch_enriched_metadata()`
4. Mettre à jour logique d'agrégation si nécessaire

Exemple :
```python
# enrichment/goodreads.py
def query_goodreads(title, isbn):
    # ... logique API
    return {"rating": 4.2, "reviews": 12000}

# enrichment/aggregator.py
def fetch_enriched_metadata(...):
    # ...
    goodreads_data = query_goodreads(title, isbn)
    result["rating"] = goodreads_data.get("rating")
    # ...
```
