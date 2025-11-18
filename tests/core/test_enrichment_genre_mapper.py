# tests/core/test_enrichment_genre_mapper.py
"""
Tests pour le module core.enrichment.genre_mapper.
"""

from epub_enricher.core.enrichment.genre_mapper import (
    GENRE_MAPPING,
    aggregate_genre,
    map_openlibrary_subject_to_genre,
    map_tags_to_genre,
)


class TestMapTagsToGenre:
    """Tests pour map_tags_to_genre."""

    def test_map_with_empty_tags(self):
        """Test avec liste de tags vide."""
        result = map_tags_to_genre([])
        assert result is None

    def test_map_with_exact_match(self):
        """Test avec match exact."""
        result = map_tags_to_genre(["Fiction"])
        assert result == "Fiction"

    def test_map_with_case_insensitive(self):
        """Test insensible à la casse."""
        result = map_tags_to_genre(["fiction"])
        assert result == "Fiction"

    def test_map_with_partial_match(self):
        """Test avec correspondance partielle."""
        result = map_tags_to_genre(["Science Fiction"])
        assert result == "Science-Fiction"

    def test_map_with_no_match(self):
        """Test sans correspondance."""
        result = map_tags_to_genre(["Unknown Genre"])
        assert result is None


class TestMapOpenlibSubjectToGenre:
    """Tests pour map_openlibrary_subject_to_genre."""

    def test_map_with_keyword_in_subject(self):
        """Test avec keyword dans le sujet."""
        result = map_openlibrary_subject_to_genre("French Fiction Literature")
        assert result == "Fiction"

    def test_map_with_no_match(self):
        """Test sans correspondance."""
        result = map_openlibrary_subject_to_genre("Unknown Subject")
        assert result is None


class TestAggregateGenre:
    """Tests pour aggregate_genre."""

    def test_aggregate_with_ol_tags_priority(self):
        """Test priorité des tags OpenLibrary."""
        result = aggregate_genre(
            ol_tags=["Fiction"], google_tags=["Science"], summary_text="Mystery story"
        )
        assert result == "Fiction"

    def test_aggregate_with_google_tags_fallback(self):
        """Test fallback sur tags Google."""
        result = aggregate_genre(ol_tags=[], google_tags=["Romance"], summary_text="")
        assert result == "Romance"

    def test_aggregate_with_text_classification_fallback(self, monkeypatch):
        """Test fallback sur classification texte."""

        # Mock classify_genre_from_text
        def mock_classify(text):
            return "Mystery"

        monkeypatch.setattr(
            "epub_enricher.core.enrichment.genre_mapper.classify_genre_from_text", mock_classify
        )

        result = aggregate_genre(ol_tags=[], google_tags=[], summary_text="This is a mystery novel")
        assert result == "Mystery"

    def test_aggregate_with_no_genre_found(self, monkeypatch):
        """Test sans genre trouvé."""

        def mock_classify(text):
            return None

        monkeypatch.setattr(
            "epub_enricher.core.enrichment.genre_mapper.classify_genre_from_text", mock_classify
        )

        result = aggregate_genre(ol_tags=[], google_tags=[], summary_text="")
        assert result is None


class TestGenreMapping:
    """Tests pour la constante GENRE_MAPPING."""

    def test_genre_mapping_structure(self):
        """Test structure du mapping."""
        assert isinstance(GENRE_MAPPING, dict)
        assert len(GENRE_MAPPING) > 0

        # Vérifier quelques genres clés
        assert "Fiction" in GENRE_MAPPING
        assert "Science-Fiction" in GENRE_MAPPING
        assert "Mystery" in GENRE_MAPPING

    def test_genre_mapping_values_are_lists(self):
        """Test que chaque valeur est une liste."""
        for genre, keywords in GENRE_MAPPING.items():
            assert isinstance(keywords, list)
            assert len(keywords) > 0
