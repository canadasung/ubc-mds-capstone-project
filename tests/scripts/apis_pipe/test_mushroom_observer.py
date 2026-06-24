"""Unit tests for the Mushroom Observer API client."""

import pytest

from scripts.apis_pipe.mushroomobs import MushroomObserverAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestMushroomObserver(BaseApiTest):
    api_class = MushroomObserverAPI
    fixture_key = "mushroom_observer"
    expected_accepted_genus = "Amanita"
    expected_accepted_species = "muscaria"

    @pytest.mark.xfail(
        strict=False,
        reason=(
            "Known MO symmetry bug: searching a synonym may not return an accepted-name "
            "row when the only non-deprecated candidate is an infraspecific name."
        ),
    )
    def test_synonym_result_has_accepted_row(self):
        super().test_synonym_result_has_accepted_row()

    @pytest.mark.xfail(
        strict=False,
        reason=(
            "Known MO symmetry bug: searching a synonym may not return an accepted-name "
            "row when the only non-deprecated candidate is an infraspecific name."
        ),
    )
    def test_accepted_and_synonym_produce_same_accepted_row(self):
        super().test_accepted_and_synonym_produce_same_accepted_row()


@pytest.fixture
def client():
    return MushroomObserverAPI()


class TestMushroomObserverExtractStatus:
    def test_deprecated_true_is_synonym(self, client):
        assert client._extract_status(True) == "Synonym"

    def test_deprecated_false_is_accepted(self, client):
        assert client._extract_status(False) == "Accepted"

    def test_none_returns_empty(self, client):
        assert client._extract_status(None) == ""


class TestMushroomObserverExtractPublicationName:
    def test_extracts_cite_content(self, client):
        assert (
            client._extract_publication_name("in <cite>Mycologia</cite> (1994)")
            == "Mycologia"
        )

    def test_no_cite_tag_returns_empty(self, client):
        assert client._extract_publication_name("no cite tag here") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_name("") == ""


class TestMushroomObserverExtractPublicationYear:
    def test_extracts_trailing_parenthesised_year(self, client):
        assert client._extract_publication_year("in <cite>Mycologia</cite> (1994)") == "1994"

    def test_no_year_returns_empty(self, client):
        assert client._extract_publication_year("in <cite>Mycologia</cite>") == ""

    def test_year_not_at_end_returns_empty(self, client):
        assert client._extract_publication_year("(1994) in text after") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_year("") == ""
