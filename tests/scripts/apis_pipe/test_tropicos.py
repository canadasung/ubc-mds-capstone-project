"""Unit tests for the Tropicos API client."""

import os
from unittest.mock import patch

import pytest

from scripts.apis_pipe.tropicos import TropicosAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


def _make_tropicos_client() -> TropicosAPI:
    """Instantiate TropicosAPI with a fake key (all fetch methods will be patched)."""
    with patch.dict(os.environ, {"TROPICOS_API_KEY": "fake-test-key"}):
        return TropicosAPI()


class TestTropicos(BaseApiTest):
    api_class = TropicosAPI
    fixture_key = "tropicos"
    expected_accepted_genus = "Quercus"
    expected_accepted_species = "robur"

    def _make_client(self):
        return _make_tropicos_client()

    def _run(self, scenario):
        """Override to also patch _fetch_accepted_list (Tropicos custom orchestrator)."""
        client = self._make_client()
        query_data = self._load(scenario, "query_data")
        accepted_list = self._load_or_none(scenario, "accepted_list_data") or []
        synonym_data = self._load_or_none(scenario, "synonym_data")
        accepted_data = self._load_or_none(scenario, "accepted_data")
        with (
            patch.object(client, "_fetch_query_data", return_value=query_data),
            patch.object(client, "_fetch_accepted_list", return_value=accepted_list),
            patch.object(client, "_fetch_synonym_data", return_value=synonym_data),
            patch.object(client, "_fetch_accepted_data", return_value=accepted_data),
        ):
            return client.get_synonyms(self._queries()[scenario])


@pytest.fixture
def tropicos_client():
    return _make_tropicos_client()


class TestTropicosExtractAuthor:
    def test_three_token_name_with_author(self, tropicos_client):
        assert tropicos_client._extract_author("Amanita muscaria (L.) Lam.") == "(L.) Lam."

    def test_two_token_name_returns_empty(self, tropicos_client):
        assert tropicos_client._extract_author("Amanita muscaria") == ""

    def test_single_token_returns_empty(self, tropicos_client):
        assert tropicos_client._extract_author("Amanita") == ""

    def test_multi_word_author_preserved(self, tropicos_client):
        assert tropicos_client._extract_author("Quercus robur L.") == "L."


class TestTropicosExtractStatus:
    def test_legitimate_maps_to_accepted(self, tropicos_client):
        assert tropicos_client._extract_status("Legitimate") == "Accepted"

    def test_synonym_falls_through_to_super(self, tropicos_client):
        assert tropicos_client._extract_status("Illegitimate synonym") == "Synonym"

    def test_unknown_returns_empty(self, tropicos_client):
        assert tropicos_client._extract_status("Unknown") == ""


class TestTropicosExtractPublicationYear:
    def test_extracts_four_digit_year(self, tropicos_client):
        assert tropicos_client._extract_publication_year("1753") == "1753"

    def test_extracts_first_four_digit_sequence(self, tropicos_client):
        assert tropicos_client._extract_publication_year("Sp. Pl. 1753") == "1753"

    def test_no_year_returns_empty(self, tropicos_client):
        assert tropicos_client._extract_publication_year("no year") == ""
