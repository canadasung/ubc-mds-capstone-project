"""Unit tests for the Paleobiology Database API client."""

import pytest

from scripts.apis_pipe.pbdb import PaleobiologyDatabaseAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestPBDB(BaseApiTest):
    api_class = PaleobiologyDatabaseAPI
    fixture_key = "pbdb"
    expected_accepted_genus = "Tyrannosaurus"
    expected_accepted_species = "rex"


class TestPBDBExtractPublicationYear:
    @pytest.fixture
    def client(self):
        return PaleobiologyDatabaseAPI()

    def test_bare_year(self, client):
        assert client._extract_publication_year("Osborn 1905") == "1905"

    def test_year_in_parentheses(self, client):
        assert client._extract_publication_year("(Paul 1988)") == "1988"

    def test_year_with_et_al(self, client):
        assert client._extract_publication_year("Paul et al. 2022") == "2022"

    def test_no_year_returns_empty(self, client):
        assert client._extract_publication_year("Unknown") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_year("") == ""


class TestPBDBExtractTaxonomy:
    @pytest.fixture
    def client(self):
        return PaleobiologyDatabaseAPI()

    def test_standard_fields(self, client):
        data = {
            "phl": "Chordata",
            "cll": "Reptilia",
            "odl": "NO_ORDER_SPECIFIED",
            "fml": "Tyrannosauridae",
        }
        result = client._extract_taxonomy(data)
        assert result["phylum"] == "Chordata"
        assert result["class_"] == "Reptilia"
        assert result["order"] == ""
        assert result["family"] == "Tyrannosauridae"

    def test_no_value_fields_cleaned(self, client):
        data = {"phl": "NO_PHYLUM_SPECIFIED", "odl": "NO_ORDER_SPECIFIED"}
        result = client._extract_taxonomy(data)
        assert result["phylum"] == ""
        assert result["order"] == ""

    def test_missing_fields_return_empty(self, client):
        result = client._extract_taxonomy({})
        assert result["phylum"] == ""
        assert result["class_"] == ""
        assert result["order"] == ""
        assert result["family"] == ""
