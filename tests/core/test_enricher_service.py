# tests/core/test_enricher_service.py
"""
Tests pour le module core.enricher_service.
"""

from unittest.mock import MagicMock, patch

from epub_enricher.core.enricher_service import EnricherService
from epub_enricher.core.models import EpubMeta


class TestEnricherServiceInit:
    """Tests pour l'initialisation du service."""

    def test_service_initialization(self):
        """Test création du service."""
        service = EnricherService()
        assert service is not None


class TestProcessEpub:
    """Tests pour process_epub."""

    @patch("epub_enricher.core.enricher_service.extract_metadata")
    @patch("epub_enricher.core.enricher_service.query_openlibrary_full")
    @patch("epub_enricher.core.enricher_service.fetch_enriched_metadata")
    def test_process_epub_success(self, mock_fetch, mock_ol, mock_extract):
        """Test traitement réussi d'un EPUB."""
        # Setup mocks
        mock_extract.return_value = {
            "title": "Test Book",
            "authors": ["Test Author"],
            "identifier": "9781234567890",
            "language": "en",
            "publisher": None,
            "date": None,
            "tags": None,
            "summary": None,
            "cover_data": None,
        }

        mock_ol.return_value = {
            "related_docs": [
                {
                    "title": "Test Book Enhanced",
                    "author_name": ["Test Author"],
                    "language": ["en"],
                    "isbn": ["9781234567890"],
                }
            ]
        }

        mock_fetch.return_value = {
            "genre": "Fiction",
            "summary": "Test summary",
            "tags": ["Fiction"],
            "cover_data": None,
            "ol_pub_date": "2024",
            "ol_publisher": "Test Publisher",
        }

        # Execute
        service = EnricherService()
        result = service.process_epub("/fake/path/test.epub")

        # Verify
        assert result is not None
        assert isinstance(result, EpubMeta)
        assert result.processed is True
        assert result.original_title == "Test Book"
        assert result.suggested_title == "Test Book Enhanced"

    @patch("epub_enricher.core.enricher_service.extract_metadata")
    def test_process_epub_with_extraction_failure(self, mock_extract):
        """Test avec échec d'extraction."""
        mock_extract.side_effect = Exception("Extraction failed")

        service = EnricherService()
        result = service.process_epub("/fake/path/test.epub")

        assert result is None

    @patch("epub_enricher.core.enricher_service.extract_metadata")
    @patch("epub_enricher.core.enricher_service.query_openlibrary_full")
    def test_process_epub_no_openlibrary_results(self, mock_ol, mock_extract):
        """Test sans résultats OpenLibrary."""
        mock_extract.return_value = {
            "title": "Test Book",
            "authors": ["Test Author"],
            "identifier": None,
            "language": None,
            "publisher": None,
            "date": None,
            "tags": None,
            "summary": None,
            "cover_data": None,
        }

        mock_ol.return_value = {"related_docs": []}

        service = EnricherService()
        result = service.process_epub("/fake/path/test.epub")

        # Doit utiliser les valeurs originales comme fallback
        assert result.suggested_title == result.original_title
        assert result.suggested_authors == result.original_authors


class TestApplyEnrichment:
    """Tests pour apply_enrichment."""

    @patch("epub_enricher.core.enricher_service.update_epub_with_metadata")
    @patch("epub_enricher.core.enricher_service.rename_epub_file")
    def test_apply_enrichment_success(self, mock_rename, mock_update):
        """Test application réussie."""
        mock_update.return_value = True

        meta = EpubMeta(
            path="/fake/path/test.epub", filename="test.epub", suggested_title="New Title"
        )

        service = EnricherService()
        result = service.apply_enrichment(meta)

        assert result is True
        mock_update.assert_called_once()
        mock_rename.assert_called_once()

    @patch("epub_enricher.core.enricher_service.update_epub_with_metadata")
    def test_apply_enrichment_failure(self, mock_update):
        """Test échec d'application."""
        mock_update.return_value = False

        meta = EpubMeta(path="/fake/path/test.epub", filename="test.epub")

        service = EnricherService()
        result = service.apply_enrichment(meta)

        assert result is False


class TestProcessFolder:
    """Tests pour process_folder."""

    @patch("epub_enricher.core.enricher_service.find_epubs_in_folder")
    @patch.object(EnricherService, "process_epub")
    def test_process_folder_multiple_files(self, mock_process, mock_find):
        """Test traitement de plusieurs fichiers."""
        mock_find.return_value = ["/folder/book1.epub", "/folder/book2.epub"]

        mock_meta1 = MagicMock(spec=EpubMeta)
        mock_meta1.processed = True
        mock_meta2 = MagicMock(spec=EpubMeta)
        mock_meta2.processed = True

        mock_process.side_effect = [mock_meta1, mock_meta2]

        service = EnricherService()
        results = service.process_folder("/folder")

        assert len(results) == 2
        assert mock_process.call_count == 2

    @patch("epub_enricher.core.enricher_service.find_epubs_in_folder")
    @patch.object(EnricherService, "process_epub")
    @patch.object(EnricherService, "apply_enrichment")
    def test_process_folder_with_autosave(self, mock_apply, mock_process, mock_find):
        """Test traitement avec autosave."""
        mock_find.return_value = ["/folder/book1.epub"]

        mock_meta = MagicMock(spec=EpubMeta)
        mock_meta.processed = True
        mock_process.return_value = mock_meta
        mock_apply.return_value = True

        service = EnricherService()
        results = service.process_folder("/folder", autosave=True)

        assert len(results) == 1
        mock_apply.assert_called_once_with(mock_meta)
