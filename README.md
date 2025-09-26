## epub-enricher

Outil Python pour enrichir des fichiers EPUB (métadonnées, traitement, etc.).

### Installation (développement)

1. Créez un environnement virtuel
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate  # Windows PowerShell
   ```
2. Installation en mode editable
   ```bash
   pip install -e .
   ```

### Utilisation

Après avoir ajouté le contenu de votre `src/epub_enricher/epub_enricher.py`, exécutez :

```bash
epub-enricher
# ou
python -m epub_enricher
```

Le point d’entrée appelle `main()` depuis `epub_enricher.epub_enricher`.

### Tests

```bash
pip install -e .[dev]
pytest -q
```

### Structure

```
epub_enricher/
├─ pyproject.toml
├─ README.md
├─ .gitignore
├─ src/
│  └─ epub_enricher/
│     ├─ __init__.py
│     ├─ __main__.py
│     └─ epub_enricher.py   # Placez ici votre fichier
└─ tests/
   └─ test_smoke.py
```

### Licence

MIT


