"""
test_COL.py — Contract tests for COL.get_checklistbank_synonyms.

All tests make real HTTP calls to the ChecklistBank API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_COL.py::TestCOLContract -v
"""

import pytest

from scripts.APIs.COL import get_checklistbank_synonyms
from tests.APIs.template_ApiTests import ApiTests


class TestCOLContract(ApiTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_checklistbank_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
