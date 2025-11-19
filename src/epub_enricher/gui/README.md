# EPUB Enricher - Module GUI 🖼️

Ce module contient l'implémentation de l'interface utilisateur graphique (GUI) de l'outil **EPUB Enricher** en utilisant la bibliothèque standard **Tkinter** de Python.

Cette interface permet aux utilisateurs de **scanner** un dossier contenant des fichiers EPUB, de **visualiser** les métadonnées originales, de **récupérer des suggestions** d'éditions (via les modules Core), et d'**éditer** puis **appliquer** les enrichissements choisis.

---

## 🏗️ Architecture MVC

Le module GUI suit le pattern **Model-View-Controller** avec séparation claire des responsabilités :

```
gui/
├── main_window.py         # 🎯 Orchestrateur (View-Controller)
├── app_controller.py      # 📊 Gestionnaire d'état (Data Controller)
├── task_manager.py        # ⚙️ Gestionnaire de threads
├── comparison_frame.py    # 📋 Panneau de comparaison
├── epub_treeview.py       # 📚 Liste des EPUBs
├── main_toolbar.py        # 🛠️ Barre d'outils
└── helpers.py             # 🔧 Utilitaires
```

---

## 📂 Structure des Fichiers

| Fichier                   | Description                                                                                                                             |
| :------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------- |
| **`main_window.py`**      | Contient la classe principale **`EnricherGUI`**, l'orchestrateur de l'interface et le gestionnaire des événements (Vue-Contrôleur).     |
| **`app_controller.py`**   | Gère l'état de l'application (la liste `EpubMeta`), le chargement et la manipulation des données, **indépendamment de l'UI**. |
| **`main_toolbar.py`**     | Composant `ttk.Frame` contenant la barre d'outils supérieure (sélection de dossier, boutons Fetch/Apply).                 |
| **`epub_treeview.py`**    | Composant `ttk.Frame` contenant le `Treeview` principal qui affiche la liste des fichiers EPUB.                           |
| **`comparison_frame.py`** | Composant `ttk.LabelFrame` pour le panneau inférieur (comparaison \"Original\" vs \"Final\", et sélection des éditions alternatives).       |
| **`task_manager.py`**     | Gère l'exécution des tâches de fond (fetch/apply) dans des threads séparés pour maintenir la réactivité de la GUI.                      |
| **`helpers.py`**          | Fonctions utilitaires, notamment le calcul de score, l'export CSV, et les helpers pour la manipulation du modèle.                       |

---

## 🎯 Logique et Rôle des Composants Clés

### `app_controller.py` : Gestionnaire d'État (Data Controller)

**Responsabilité** : Source de vérité pour les données.

```python
class AppController:
    def __init__(self):
        self.meta_list: List[EpubMeta] = []
        
    def load_from_folder(self, folder_path: str) -> List[EpubMeta]
    def get_meta_by_index(self, index: int) -> Optional[EpubMeta]
    def get_metas_by_indices(self, indices: List[int]) -> List[EpubMeta]
    def reset_metas(self, metas: List[EpubMeta])
```

**Caractéristiques** :
- ✅ Ne contient **aucune logique Tkinter**
- ✅ Gère la liste `meta_list` (état global)
- ✅ Testable unitairement
- ✅ Réutilisable (pourrait être partagé avec une autre UI)

### `main_window.py` : Orchestrateur GUI (Vue-Contrôleur)

**Responsabilité** : Assembler les composants et gérer les interactions.

**Flux typique** :
1. **Assemblage** : Crée `MainToolbar`, `EpubTreeview`, `ComparisonFrame`
2. **État** : Possède une instance de `AppController`
3. **Événements** : Gère les callbacks (ex: clic sur \"Fetch\")
4. **Délégation** :
   - Demande données au `AppController`
   - Lance tâches via `task_manager`
   - Met à jour les vues

**Séparation des préoccupations** :
- Pas de logique métier (déléguée au core)
- Pas de gestion directe des données (déléguée à `AppController`)
- Focus sur l'orchestration UI

### `main_toolbar.py` et `epub_treeview.py` : Composants de Vue

**Responsabilité** : Affichage et remontée d'événements.

**Caractéristiques** :
- Composants `ttk.Frame` "passifs"
- Affichent les données fournies
- Remontent événements via callbacks
- Pas de logique métier

**Exemple** (`epub_treeview.py`) :
```python
class EpubTreeview(ttk.Frame):
    def __init__(self, parent, on_select_callback):
        # ... création du Treeview
        self.tree.bind("<<TreeviewSelect>>", on_select_callback)
    
    def load_data(self, metas: List[EpubMeta]):
        # Remplit le Treeview avec les données
```

### `comparison_frame.py` : Panneau d'Édition et Sélection

**Responsabilité** : Comparaison et édition des métadonnées.

**Fonctionnalités** :
- Affiche côte à côte : "Original" (lecture seule) vs "Valeur à appliquer" (éditable)
- Affiche les couvertures (originale + suggérée)
- Liste les éditions alternatives (`meta.found_editions`)
- Gère la sélection d'une édition alternative

**Méthodes clés** :
```python
def load_meta(self, meta: EpubMeta):
    """Charge un EpubMeta dans le panneau."""
    
def save_final_values_to_model(self):
    """Sauvegarde les valeurs éditées dans le modèle."""
    
def _on_edition_selected_from_tree(self, event):
    """Peuple les champs avec l'édition sélectionnée."""
```

### `task_manager.py` : Gestionnaire de Threads

**Responsabilité** : Exécuter les tâches longues sans bloquer l'UI.

**Workers** :
- `_fetch_worker` : Appelle les APIs, met à jour `suggested_...` et `found_editions`
- `_apply_worker` : Écrit les EPUBs, applique les changements
- `_cover_download_worker` : Télécharge les couvertures en arrière-plan

**Pattern** :
1. Lance le worker dans un thread séparé
2. Worker met à jour les données
3. Appelle `schedule_gui_refresh()` sur le thread principal (Tkinter-safe)

**Exemple** :
```python
def fetch_for_metas(self, metas: List[EpubMeta], callback):
    """Lance le fetch dans un thread."""
    thread = threading.Thread(
        target=self._fetch_worker,
        args=(metas, callback)
    )
    thread.start()
```

### `helpers.py` : Fonctions Utilitaires

**Fonctions principales** :
- `apply_suggestions_to_model(meta)` : Copie `suggested_` → `original_` après application
- `reset_suggestions_on_model(meta)` : Efface les suggestions
- `export_to_csv(metas, filepath)` : Exporte l'état actuel
- `calculate_metadata_score(meta)` : Calcule un score de complétude

**Caractéristiques** :
- ✅ Fonctions pures (pas d'état)
- ✅ Testables unitairement
- ✅ Réutilisables

---

## 🔄 Flux d'Utilisation Typique

### 1. Scanner un Dossier

```
User clique "Select & Scan Folder"
  ↓
main_window._on_select_folder()
  ↓
app_controller.load_from_folder(path)
  ↓
epub_treeview.load_data(metas)
```

### 2. Fetch Suggestions

```
User sélectionne EPUB + clique "Fetch"
  ↓
main_window._on_fetch()
  ↓
task_manager.fetch_for_metas(metas)
  ↓
[Thread] Appels APIs (OpenLibrary, Google, Wikipedia)
  ↓
[Thread] Met à jour meta.suggested_...
  ↓
schedule_gui_refresh()
  ↓
epub_treeview rafraîchi avec nouvelles données
```

### 3. Éditer et Appliquer

```
User sélectionne EPUB dans Treeview
  ↓
comparison_frame.load_meta(meta)
  ↓
User édite manuellement OU sélectionne édition alternative
  ↓
User clique "Apply Changes"
  ↓
comparison_frame.save_final_values_to_model()
  ↓
task_manager.apply_for_metas(metas)
  ↓
[Thread] Écrit les EPUBs
  ↓
[Thread] helpers.apply_suggestions_to_model()
  ↓
[Thread] helpers.reset_suggestions_on_model()
```

---

## 🧪 Intégration avec Core

La GUI utilise `EnricherService` (Service Layer) pour toutes les opérations métier :

```python
# Dans task_manager.py
from ..core.enricher_service import EnricherService

service = EnricherService()

# Fetch
meta = service.process_epub(epub_path)

# Apply
success = service.apply_enrichment(meta)
```

**Avantages** :
- ✅ Pas de duplication avec le CLI
- ✅ Logique métier centralisée
- ✅ Tests du core = tests de la GUI indirects

---

## 📊 Métriques

**Complexité** :
- `main_window.py` : ~300 lignes (orchestration)
- `comparison_frame.py` : ~590 lignes (UI complexe)
- `app_controller.py` : ~113 lignes (état simple)

**Séparation des préoccupations** : ✅ Excellente
- Core isolé (0 import Tkinter dans core/)
- Modèle séparé de la vue
- Threading isolé dans task_manager

---

## 🚀 Extension

**Ajouter un nouveau panneau** :

1. Créer `nouveau_panneau.py` héritant de `ttk.Frame`
2. Défini callbacks pour remonter événements
3. Intégrer dans `main_window.py`
4. Utiliser `app_controller` pour accéder aux données

**Exemple** :
```python
# statistics_panel.py
class StatisticsPanel(ttk.Frame):
    def __init__(self, parent, controller: AppController):
        super().__init__(parent)
        self.controller = controller
        self.create_widgets()
    
    def refresh(self):
        metas = self.controller.meta_list
        # Calculer et afficher statistiques
```
