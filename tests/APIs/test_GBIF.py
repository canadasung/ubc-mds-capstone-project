"""
test_GBIF.py — Contract tests for GBIF.get_gbif_synonyms.

All tests make real calls to the GBIF API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_GBIF.py::TestGBIFContract -v
"""

import pytest

from scripts.APIs.GBIF import get_gbif_synonyms
from tests.APIs.template_ApiTests import ApiTests


class TestGBIFContract(ApiTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_gbif_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
