"""Unit tests for the GBIF API client."""

import pytest

from scripts.apis_pipe.gbif import GBIFAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestGBIF(BaseApiTest):
    api_class = GBIFAPI
    fixture_key = "gbif"
    expected_accepted_genus = "Amanita"
    expected_accepted_species = "muscaria"


class TestGBIFExtractPublicationYear:
    @pytest.fixture
    def client(self):
        return GBIFAPI()

    def test_year_in_parentheses_in_published_in(self, client):
        assert client._extract_publication_year("(1788). Hist. Fung. Halifax 2: 46", "") == "1788"

    def test_fallback_to_bare_year_in_author(self, client):
        assert client._extract_publication_year("Hist. Fung. Halifax", "Suckley, 1860") == "1860"

    def test_published_in_takes_priority_over_author(self, client):
        assert client._extract_publication_year("(1788). text", "L., 1753") == "1788"

    def test_no_year_returns_empty(self, client):
        assert client._extract_publication_year("no year here", "") == ""

    def test_both_empty_returns_empty(self, client):
        assert client._extract_publication_year("", "") == ""
