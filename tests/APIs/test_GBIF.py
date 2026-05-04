"""
test_GBIF.py — Contract tests for GBIF.get_gbif_synonyms.

All tests make real calls to the GBIF API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_GBIF.py::TestGBIFContract -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from GBIF import get_gbif_synonyms
from test_API import ApiContractTests


class TestGBIFContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_gbif_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
