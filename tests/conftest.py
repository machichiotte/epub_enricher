# tests/conftest.py
"""
Configuration globale pour pytest.

Fournit des fixtures réutilisables pour tous les tests.
"""

import os
from pathlib import Path
from typing import Dict

import pytest


@pytest.fixture
def sample_epub_metadata() -> Dict:
    """Retourne des métadonnées d'exemple pour tests."""
    return {
        "title": "Test Book",
        "authors": ["Test Author"],
        "language": "en",
        "identifier": "9781234567890",
        "publisher": "Test Publisher",
        "date": "2024",
        "tags": ["Fiction", "Test"],
        "summary": "This is a test book summary.",
        "cover_data": None,
    }


@pytest.fixture
def sample_epub_meta_object():
    """Retourne un objet EpubMeta d'exemple pour tests."""
    from epub_enricher.core.models import EpubMeta
    
    return EpubMeta(
        path="/fake/path/test.epub",
        filename="test.epub",
        original_title="Original Title",
        original_authors=["Original Author"],
        original_isbn="9780000000000",
        original_language="en",
        suggested_title="Suggested Title",
        suggested_authors=["Suggested Author"],
        suggested_isbn="9781111111111",
        suggested_language="fr",
    )


@pytest.fixture
def temp_dir(tmp_path):
    """Fournit un répertoire temporaire pour les tests."""
    return tmp_path


@pytest.fixture
def mock_http_response():
    """Retourne un mock de réponse HTTP."""
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code
            self.text = str(json_data)
        
        def json(self):
            return self.json_data
    
    return MockResponse
