# epub_enricher/src/epub_enricher/core/text_utils.py
"""
Utilitaires pour le nettoyage et l'analyse de chaînes de caractères.
"""

import re
from typing import Dict, Optional

# Mots-clés pour la classification (en français, car l'API Wikipedia est 'fr')
_CLASSIFICATION_KEYWORDS = {
    "Fiction": ["roman", "histoire", "personnage", "intrigue", "fiction"],
    "Science-Fiction": ["espace", "futur", "robot", "alien", "planète", "science fiction"],
    "Fantasy": ["magie", "sorcier", "dragon", "fantaisie", "enchanteur", "fantasy"],
    "Mystery": ["détective", "crime", "mystère", "enquête", "policier", "mystery"],
    "Romance": ["amour", "romance", "cœur", "passion", "couple", "love"],
    "Thriller": ["suspense", "tension", "danger", "poursuite", "menace", "thriller"],
    "Biography": ["vie", "biographie", "autobiographie", "mémoires", "biography"],
    "History": ["historique", "guerre", "époque", "siècle", "batailles", "history"],
    "Philosophy": ["philosophie", "philosophique", "philosophy"],
    "Science": ["science", "scientifique", "science"],
    "Art": ["art", "artistique", "art"],
    "Poetry": ["poésie", "poème", "poetry"],
}


def clean_html_text(html_content: str) -> str:
    """Nettoie le HTML pour extraire le texte."""
    if not html_content:
        return ""
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Nettoie le texte général."""
    if not text:
        return ""
    # Supprimer les caractères spéciaux (garder ponctuation basique)
    text = re.sub(r"[^\w\s.,!?;:-]", " ", text)
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_genre_from_text(text: str) -> Optional[str]:
    """Classification automatique du genre basée sur le texte."""
    if not text:
        return None

    text_lower = text.lower()
    genre_scores: Dict[str, int] = {}

    # Compter les occurrences
    for genre, keywords in _CLASSIFICATION_KEYWORDS.items():
        score = sum(text_lower.count(keyword) for keyword in keywords)
        if score > 0:
            genre_scores[genre] = score

    # Retourner le genre avec le score le plus élevé (seuil minimum de 1)
    if genre_scores:
        best_genre = max(genre_scores, key=genre_scores.get)
        if genre_scores[best_genre] >= 1:
            return best_genre

    return None
