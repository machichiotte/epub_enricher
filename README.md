# EPUB Enricher

Outil Python complet pour enrichir automatiquement les métadonnées des fichiers EPUB en utilisant l'API OpenLibrary. L'application propose une interface graphique intuitive et un mode ligne de commande pour traiter des collections entières de livres électroniques.

## 🚀 Fonctionnalités

### Métadonnées enrichies

-   **Titre** : Recherche et correction automatique
-   **Auteurs** : Identification et normalisation des noms
-   **ISBN** : Validation et correction des codes ISBN
-   **Langue** : Détection automatique de la langue du contenu
-   **Éditeur** : Récupération des informations d'édition
-   **Date de publication** : Extraction des dates
-   **Couverture** : Téléchargement et intégration des images de couverture

### Modes d'utilisation

-   **Interface graphique** : Interface Tkinter complète avec comparaison côte à côte
-   **Ligne de commande** : Traitement par lots avec options d'automatisation
-   **Export CSV** : Sauvegarde des métadonnées pour analyse

### Sécurité et fiabilité

-   **Sauvegarde automatique** : Création de copies de sécurité avant modification
-   **Système de retry** : Gestion robuste des erreurs réseau avec backoff exponentiel
-   **Cache des images** : Évite les téléchargements répétés
-   **Logging complet** : Traçabilité de toutes les opérations

## 🏗️ Architecture

Le projet suit une architecture modulaire avec séparation stricte des responsabilités (SOC/SOR). Consultez [`docs/architecture.md`](docs/architecture.md) pour les détails complets.

### Structure des Modules

```
epub_enricher/
├── core/                    # Logique métier
│   ├── epub/               # Manipulation EPUB
│   │   ├── reader.py       # Extraction métadonnées
│   │   ├── writer.py       # Écriture métadonnées
│   │   ├── cover_finder.py # Recherche couverture (Strategy pattern)
│   │   └── metadata_extractors.py
│   ├── enrichment/         # APIs externes
│   │   ├── google_books.py
│   │   ├── wikipedia.py
│   │   ├── aggregator.py   # Orchestration
│   │   └── genre_mapper.py
│   ├── enricher_service.py # Service Layer (réutilisable CLI/GUI)
│   ├── metadata_fetcher.py # Client OpenLibrary
│   └── models.py           # EpubMeta dataclass
├── gui/                     # Interface graphique (MVC)
│   ├── main_window.py
│   ├── app_controller.py
│   └── task_manager.py     # Threading
└── cli.py                   # Interface CLI
```

### Utilisation Programmatique

```python
# Nouveau: Imports recommandés depuis les modules refactorisés
from epub_enricher.core.epub import extract_metadata, update_epub_with_metadata
from epub_enricher.core.enrichment import fetch_enriched_metadata
from epub_enricher.core.enricher_service import EnricherService

# Service Layer (recommandé)
service = EnricherService()
meta = service.process_epub("path/to/book.epub")
service.apply_enrichment(meta)
```

## 📦 Installation

### Prérequis

-   Python 3.10 ou supérieur
-   Connexion internet (pour l'API OpenLibrary)

### Installation en mode développement

1. **Cloner le projet**

    ```bash
    git clone <repository-url>
    cd epub_enricher
    ```

2. **Créer un environnement virtuel**

    ```bash
    python -m venv .venv
    .venv\Scripts\activate  # Windows PowerShell
    # ou
    source .venv/bin/activate  # Linux/macOS
    ```

3. **Installer en mode éditable**
    ```bash
    pip install -e .
    ```

### Installation des dépendances de développement

```bash
pip install -e .[dev]
```

## 🖥️ Utilisation

### Mode Interface Graphique (par défaut)

Lancez l'application avec l'interface graphique :

```bash
epub-enricher
# ou
python -m epub_enricher
```

**Workflow typique :**

1. **Sélectionner un dossier** contenant vos fichiers EPUB
2. **Scanner** pour extraire les métadonnées existantes
3. **Récupérer les suggestions** depuis OpenLibrary
4. **Comparer** les métadonnées originales et suggérées
5. **Accepter/Rejeter** les suggestions individuellement
6. **Appliquer** les changements acceptés
7. **Exporter** un rapport CSV si nécessaire

### Mode Ligne de Commande

Pour un traitement automatisé :

```bash
# Traitement simple (sans modification)
python -m epub_enricher /chemin/vers/dossier/epub

# Traitement avec application automatique des suggestions
python -m epub_enricher /chemin/vers/dossier/epub --autosave

# Mode CLI forcé (variable d'environnement)
EPUB_ENRICHER_NO_GUI=1 python -m epub_enricher /chemin/vers/dossier/epub
```

## 🏗️ Architecture du Projet

Le projet suit une architecture modulaire bien structurée :

```
epub_enricher/
├── pyproject.toml              # Configuration du projet et dépendances
├── README.md                   # Documentation principale
├── REFACTOR_STRUCTURE.md       # Documentation de l'architecture
├── src/
│   └── epub_enricher/
│       ├── __init__.py
│       ├── __main__.py         # Point d'entrée CLI
│       ├── main.py             # Point d'entrée principal (GUI/CLI)
│       ├── config.py           # Configuration et constantes
│       ├── cli.py              # Logique du mode ligne de commande
│       ├── core/               # Logique métier
│       │   ├── __init__.py
│       │   ├── models.py       # Modèles de données (EpubMeta)
│       │   ├── epub_processor.py  # Traitement des fichiers EPUB
│       │   └── metadata_fetcher.py # API OpenLibrary et cache
│       └── gui/                # Interface utilisateur
│           ├── __init__.py
│           └── main_window.py  # Interface Tkinter complète
└── tests/
    └── test_smoke.py           # Tests de base
```

### Modules principaux

#### `core/models.py`

Définit la structure `EpubMeta` qui encapsule toutes les métadonnées d'un fichier EPUB, incluant les valeurs originales et suggérées.

#### `core/epub_processor.py`

-   Extraction des métadonnées depuis les fichiers EPUB
-   Mise à jour des fichiers avec les nouvelles métadonnées
-   Gestion des sauvegardes automatiques
-   Détection automatique de la langue

#### `core/metadata_fetcher.py`

-   Intégration avec l'API OpenLibrary
-   Système de retry avec backoff exponentiel
-   Cache des images de couverture
-   Gestion robuste des erreurs réseau

#### `gui/main_window.py`

Interface graphique complète avec :

-   Vue en tableau des fichiers EPUB
-   Comparaison côte à côte des métadonnées
-   Aperçu des couvertures
-   Gestion des sélections multiples
-   Export CSV

## ⚙️ Configuration

### Variables d'environnement

-   `EPUB_ENRICHER_NO_GUI=1` : Force le mode ligne de commande

### Dossiers créés automatiquement

-   `logs/` : Fichiers de log avec rotation
-   `backups/` : Sauvegardes des fichiers modifiés
-   `.cover_cache/` : Cache des images de couverture

### Configuration réseau

-   Timeout API : 10 secondes
-   Retry maximum : 5 tentatives
-   Backoff initial : 1 seconde
-   Backoff maximum : 30 secondes

## 🧪 Tests

Exécuter les tests :

```bash
pytest -q
```

## 📊 Exemples d'utilisation

### Traitement d'une bibliothèque personnelle

```bash
# Scanner et enrichir tous les EPUBs d'un dossier
python -m epub_enricher "C:\Users\MonNom\Documents\Livres" --autosave
```

### Export pour analyse

1. Lancez l'interface graphique
2. Scannez votre dossier
3. Récupérez les suggestions
4. Exportez en CSV pour analyse externe

### Traitement par lots avec logs

```bash
# Mode CLI avec logs détaillés
EPUB_ENRICHER_NO_GUI=1 python -m epub_enricher /path/to/books 2>&1 | tee processing.log
```

## 🔧 Développement

### Structure modulaire

Le projet a été refactorisé pour une meilleure maintenabilité :

-   Séparation claire des responsabilités
-   Code testable et réutilisable
-   Architecture évolutive

### Ajout de nouvelles fonctionnalités

1. **Nouvelles métadonnées** : Modifier `core/models.py`
2. **Nouvelles APIs** : Étendre `core/metadata_fetcher.py`
3. **Nouvelle interface** : Créer dans `gui/` ou `cli/`

### Formatage du code

```bash
# Black pour le formatage
black src/

# Ruff pour le linting
ruff check src/
```

## 🐛 Dépannage

### Problèmes courants

1. **Erreur de connexion API** : Vérifiez votre connexion internet
2. **Fichiers corrompus** : Les sauvegardes sont dans `backups/`
3. **Images non affichées** : Vérifiez l'installation de Pillow

### Logs

Consultez `logs/epub_enricher.log` pour des informations détaillées.

## 📄 Licence

MIT License - Voir le fichier `LICENSE` pour plus de détails.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

-   Signaler des bugs
-   Proposer des améliorations
-   Soumettre des pull requests

## 📞 Support

Pour toute question ou problème, consultez les logs ou créez une issue sur le repository.
