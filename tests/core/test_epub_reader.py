# tests/core/test_epub_reader.py
"""
Tests pour le module core.epub.reader.
"""

import pytest
from epub_enricher.core.epub.reader import (
    _get_authors,
    _get_identifier,
    _get_language,
    _get_tags,
    _get_title,
    extract_metadata,
    safe_read_epub,
)


class TestSafeReadEpub:
    """Tests pour safe_read_epub."""
    
    def test_safe_read_epub_nonexistent_file(self):
        """Test qu'un fichier inexistant retourne None."""
        result = safe_read_epub("/fake/path/nonexistent.epub")
        assert result is None
    
    def test_safe_read_epub_invalid_file(self, tmp_path):
        """Test qu'un fichier invalide retourne None."""
        invalid_file = tmp_path / "invalid.epub"
        invalid_file.write_text("This is not an EPUB")
        
        result = safe_read_epub(str(invalid_file))
        assert result is None


class TestExtractMetadata:
    """Tests pour extract_metadata."""
    
    def test_extract_metadata_nonexistent_file(self):
        """Test extraction avec fichier inexistant."""
        result = extract_metadata("/fake/path/nonexistent.epub")
        
        # Doit retourner un dict avec toutes les clés à None
        assert result is not None
        assert isinstance(result, dict)
        assert result["title"] is None
        assert result["authors"] is None
        assert result["identifier"] is None
    
    def test_extract_metadata_returns_all_keys(self):
        """Test que tous les champs attendus sont présents."""
        result = extract_metadata("/fake/path/test.epub")
        
        expected_keys = {
            "title", "authors", "language", "identifier",
            "publisher", "date", "tags", "summary", "cover_data"
        }
        assert set(result.keys()) == expected_keys


class TestMetadataExtractors:
    """Tests pour les extracteurs de métadonnées individuels."""
    
    def test_get_title_with_none(self):
        """Test _get_title avec book None."""
        # Mock d'un book object minimal
        class MockBook:
            def get_metadata(self, ns, name):
                return None
        
        result = _get_title(MockBook())
        assert result is None
    
    def test_get_authors_with_empty_metadata(self):
        """Test _get_authors avec métadonnées vides."""
        class MockBook:
            def get_metadata(self, ns, name):
                return []
        
        result = _get_authors(MockBook())
        assert result is None
    
    def test_get_tags_with_empty_metadata(self):
        """Test _get_tags avec métadonnées vides."""
        class MockBook:
            def get_metadata(self, ns, name):
                return []
        
        result = _get_tags(MockBook())
        assert result is None
