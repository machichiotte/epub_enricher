# tests/test_cli.py
"""
Tests pour le module CLI.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from epub_enricher.cli import cli_process_folder, print_metadata_summary
from epub_enricher.core.models import EpubMeta


class TestCliProcessFolder:
    """Tests pour cli_process_folder."""
    
    @patch('epub_enricher.cli.EnricherService')
    def test_cli_process_folder_basic(self, mock_service_class):
        """Test traitement basique d'un dossier."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        mock_meta = MagicMock(spec=EpubMeta)
        mock_service.process_folder.return_value = [mock_meta]
        
        result = cli_process_folder("/fake/folder")
        
        assert len(result) == 1
        mock_service.process_folder.assert_called_once_with("/fake/folder", autosave=False)
    
    @patch('epub_enricher.cli.EnricherService')
    def test_cli_process_folder_with_autosave(self, mock_service_class):
        """Test avec autosave activé."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.process_folder.return_value = []
        
        cli_process_folder("/fake/folder", autosave=True)
        
        mock_service.process_folder.assert_called_once_with("/fake/folder", autosave=True)


class TestPrintMetadataSummary:
    """Tests pour print_metadata_summary."""
    
    def test_print_empty_list(self, capsys):
        """Test affichage avec liste vide."""
        print_metadata_summary([])
        
        captured = capsys.readouterr()
        assert "Fichiers traités: 0" in captured.out
    
    def test_print_with_processed_metadata(self, capsys):
        """Test affichage avec métadonnées traitées."""
        meta = EpubMeta(
            path="/fake/test.epub",
            filename="test.epub",
            original_title="Original",
            original_authors=["Author1"],
            suggested_title="Suggested",
            suggested_authors=["Author2"],
            processed=True
        )
        
        print_metadata_summary([meta])
        
        captured = capsys.readouterr()
        assert "Fichiers traités: 1" in captured.out
        assert "Avec suggestions: 1" in captured.out
        assert "test.epub" in captured.out
    
    def test_print_with_no_changes(self, capsys):
        """Test affichage sans changements."""
        meta = EpubMeta(
            path="/fake/test.epub",
            filename="test.epub",
            original_title="Same Title",
            original_authors=["Same Author"],
            suggested_title="Same Title",
            suggested_authors=["Same Author"],
            processed=True
        )
        
        print_metadata_summary([meta])
        
        captured = capsys.readouterr()
        # Ne doit pas afficher de changements car tous identiques
        assert "Fichiers traités: 1" in captured.out
    
    def test_print_with_multiple_files(self, capsys):
        """Test affichage avec plusieurs fichiers."""
        metas = [
            EpubMeta(
                path=f"/fake/test{i}.epub",
                filename=f"test{i}.epub",
                processed=(i % 2 == 0)
            )
            for i in range(5)
        ]
        
        print_metadata_summary(metas)
        
        captured = capsys.readouterr()
        assert "Fichiers traités: 5" in captured.out
        assert "Avec suggestions: 3" in captured.out  # 0, 2, 4
