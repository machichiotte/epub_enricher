# Structure Refactorisée d'EPUB Enricher

## Vue d'ensemble

Le projet a été refactorisé pour améliorer l'organisation du code et la maintenabilité. Le fichier monolithique `epub_enricher.py` a été divisé en plusieurs modules spécialisés.

## Nouvelle Structure

```
epub_enricher/
├── main.py              # Point d'entrée : décide de lancer le GUI ou le CLI
├── config.py            # Constantes et configuration (URLs, noms de dossiers, etc.)
├── core/
│   ├── __init__.py
│   ├── models.py        # Classes de données (ex: EpubMeta)
│   ├── epub_processor.py  # Logique métier pour lire/écrire les EPUBs
│   └── metadata_fetcher.py# Logique pour interroger les APIs (OpenLibrary)
├── gui/
│   ├── __init__.py
│   └── main_window.py   # Tout le code de l'interface Tkinter
└── cli.py               # La logique pour le mode ligne de commande
```

## Modules

### `main.py`

-   Point d'entrée principal de l'application
-   Configure le logging
-   Décide entre mode GUI et CLI selon l'environnement
-   Gère les arguments de ligne de commande

### `config.py`

-   Toutes les constantes et configurations
-   URLs des APIs
-   Chemins des dossiers
-   Paramètres de retry/backoff
-   Configuration du logging et de l'interface

### `core/models.py`

-   Classes de données : `EpubMeta`
-   Structure des métadonnées EPUB

### `core/epub_processor.py`

-   Logique métier pour les fichiers EPUB
-   Extraction de métadonnées
-   Sauvegarde et mise à jour des fichiers
-   Gestion des erreurs

### `core/metadata_fetcher.py`

-   Interrogation des APIs externes (OpenLibrary)
-   Téléchargement de couvertures
-   Système de retry avec backoff exponentiel
-   Cache des images

### `gui/main_window.py`

-   Interface utilisateur Tkinter complète
-   Gestion des événements
-   Threading pour les opérations longues
-   Export CSV

### `cli.py`

-   Mode ligne de commande
-   Traitement par lots
-   Résumé des résultats

## Avantages de la Refactorisation

1. **Séparation des responsabilités** : Chaque module a un rôle précis
2. **Maintenabilité** : Code plus facile à comprendre et modifier
3. **Testabilité** : Modules isolés plus faciles à tester
4. **Réutilisabilité** : Composants réutilisables dans d'autres projets
5. **Évolutivité** : Structure modulaire pour ajouter de nouvelles fonctionnalités

## Utilisation

### Mode GUI (par défaut)

```bash
python -m epub_enricher
```

### Mode CLI

```bash
# Traitement simple
python -m epub_enricher /path/to/epub/folder

# Avec application automatique des suggestions
python -m epub_enricher /path/to/epub/folder --autosave

# Mode CLI forcé (variable d'environnement)
EPUB_ENRICHER_NO_GUI=1 python -m epub_enricher
```

## Migration

L'ancien fichier `epub_enricher.py` peut être conservé temporairement pour référence, mais la nouvelle structure doit être utilisée pour tout nouveau développement.
