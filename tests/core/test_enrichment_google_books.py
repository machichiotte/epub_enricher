# tests/core/test_enrichment_google_books.py
"""
Tests pour le module core.enrichment.google_books.
"""

import pytest
from unittest.mock import Mock, patch

from epub_enricher.core.enrichment.google_books import (
    _parse_google_book,
    query_google_books,
)


class TestParseGoogleBook:
    """Tests pour _parse_google_book."""
    
    def test_parse_with_full_data(self):
        """Test parsing avec données complètes."""
        item = {
            "volumeInfo": {
                "description": "<p>Test description</p>",
                "categories": ["Fiction", "Mystery"],
            }
        }
        
        result = _parse_google_book(item)
        
        assert "summary" in result
        assert "Test description" in result["summary"]
        assert "tags" in result
        assert len(result["tags"]) == 2
    
    def test_parse_with_minimal_data(self):
        """Test parsing avec données minimales."""
        item = {"volumeInfo": {}}
        
        result = _parse_google_book(item)
        
        assert isinstance(result, dict)
        assert result.get("summary") == ""
    
    def test_parse_with_subjects_instead_of_categories(self):
        """Test parsing avec subjects au lieu de categories."""
        item = {
            "volumeInfo": {
                "subjects": ["Science", "Technology"],
            }
        }
        
        result = _parse_google_book(item)
        
        assert "tags" in result
        assert len(result["tags"]) == 2


class TestQueryGoogleBooks:
    """Tests pour query_google_books."""
    
    def test_query_without_title_or_isbn(self):
        """Test query sans titre ni ISBN."""
        result = query_google_books()
        assert result == {}
    
    @patch('epub_enricher.core.enrichment.google_books.http_get')
    def test_query_with_isbn(self, mock_http_get):
        """Test query avec ISBN."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{
                "volumeInfo": {
                    "description": "Test book",
                    "categories": ["Fiction"]
                }
            }]
        }
        mock_http_get.return_value = mock_response
        
        result = query_google_books(isbn="9781234567890")
        
        assert "summary" in result
        assert "tags" in result
        mock_http_get.assert_called_once()
    
    @patch('epub_enricher.core.enrichment.google_books.http_get')
    def test_query_with_no_results(self, mock_http_get):
        """Test query sans résultats."""
        mock_response = Mock()
        mock_response.json.return_value = {"items": None}
        mock_http_get.return_value = mock_response
        
        result = query_google_books(title="Nonexistent Book")
        
        assert result == {}
    
    @patch('epub_enricher.core.enrichment.google_books.http_get')
    def test_query_with_api_error(self, mock_http_get):
        """Test query avec erreur API."""
        mock_http_get.side_effect = Exception("API Error")
        
        result = query_google_books(title="Test Book")
        
        assert result == {}
