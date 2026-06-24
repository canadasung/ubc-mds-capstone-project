"""Unit tests for the COL API client."""

import pytest

from scripts.apis_pipe.col import COLAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestCOL(BaseApiTest):
    api_class = COLAPI
    fixture_key = "col"
    expected_accepted_genus = "Quercus"
    expected_accepted_species = "robur"


class TestCOLExtractTaxonomy:
    @pytest.fixture
    def client(self):
        return COLAPI()

    def test_extracts_known_ranks(self, client):
        data = {
            "usage": {
                "classification": [
                    {"rank": "kingdom", "name": "Plantae"},
                    {"rank": "phylum", "name": "Tracheophyta"},
                    {"rank": "family", "name": "Fagaceae"},
                ]
            }
        }
        result = client._extract_taxonomy(data)
        assert result["kingdom"] == "Plantae"
        assert result["phylum"] == "Tracheophyta"
        assert result["family"] == "Fagaceae"

    def test_missing_ranks_return_empty_string(self, client):
        data = {"usage": {"classification": [{"rank": "kingdom", "name": "Plantae"}]}}
        result = client._extract_taxonomy(data)
        assert result["phylum"] == ""
        assert result["order"] == ""

    def test_top_level_classification_key(self, client):
        data = {
            "classification": [{"rank": "kingdom", "name": "Animalia"}]
        }
        result = client._extract_taxonomy(data)
        assert result["kingdom"] == "Animalia"

    def test_empty_classification_returns_all_empty(self, client):
        data = {"usage": {"classification": []}}
        result = client._extract_taxonomy(data)
        assert all(v == "" for v in result.values())
