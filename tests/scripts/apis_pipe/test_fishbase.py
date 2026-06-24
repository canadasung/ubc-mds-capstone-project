"""Unit tests for the FishBase API client."""

import pytest

from scripts.apis_pipe.fishbase import FishBaseAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestFishBase(BaseApiTest):
    api_class = FishBaseAPI
    fixture_key = "fishbase"
    expected_accepted_genus = "Gadus"
    expected_accepted_species = "morhua"


class TestFishBaseExtractAuthor:
    @pytest.fixture
    def client(self):
        return FishBaseAPI()

    def test_not_given_returns_empty(self, client):
        assert client._extract_author("not given") == ""

    def test_not_given_case_insensitive(self, client):
        assert client._extract_author("NOT GIVEN") == ""
        assert client._extract_author("Not Given") == ""

    def test_real_author_unchanged(self, client):
        assert client._extract_author("Linnaeus, 1758") == "Linnaeus, 1758"

    def test_empty_string_unchanged(self, client):
        assert client._extract_author("") == ""


class TestFishBaseExtractPublicationYear:
    @pytest.fixture
    def client(self):
        return FishBaseAPI()

    def test_strips_year_suffix(self, client):
        assert client._extract_publication_year("Linnaeus, 1758") == "1758"

    def test_no_year_returns_empty(self, client):
        assert client._extract_publication_year("Linnaeus") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_year("") == ""


class TestFishBaseExtractSynonymParams:
    @pytest.fixture
    def client(self):
        return FishBaseAPI()

    def test_parses_synonym_link(self, client):
        html = (
            '<a href="SynonymSummary.php?GenusName=Gadus&SpeciesName=morhua'
            '&Author=Linnaeus&Status=accepted name&SpecCode=69">link</a>'
        )
        params = client._extract_synonym_params(html)
        assert len(params) == 1
        assert params[0]["GenusName"] == "Gadus"
        assert params[0]["SpeciesName"] == "morhua"
        assert params[0]["Author"] == "Linnaeus"
        assert params[0]["Status"] == "accepted name"
        assert params[0]["SpecCode"] == "69"

    def test_multiple_links_parsed(self, client):
        html = (
            '<a href="SynonymSummary.php?GenusName=Gadus&SpeciesName=morhua">a</a>'
            '<a href="SynonymSummary.php?GenusName=Gadus&SpeciesName=callarias">b</a>'
        )
        params = client._extract_synonym_params(html)
        assert len(params) == 2

    def test_no_links_returns_empty_list(self, client):
        assert client._extract_synonym_params("<html><body></body></html>") == []


class TestFishBaseExtractAcceptedName:
    @pytest.fixture
    def client(self):
        return FishBaseAPI()

    def test_extracts_from_og_url(self, client):
        html = (
            '<meta property="og:url" '
            'content="https://www.fishbase.se/summary/Gadus-morhua.html" />'
        )
        genus, species = client._extract_accepted_name(html)
        assert genus == "Gadus"
        assert species == "morhua"

    def test_falls_back_to_provided_values(self, client):
        genus, species = client._extract_accepted_name(
            "<html></html>", fallback_genus="Gadus", fallback_species="morhua"
        )
        assert genus == "Gadus"
        assert species == "morhua"
