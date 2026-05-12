"""
test_Macroalgae.py — Contract tests for Macroalgae.get_macroalgae_synonyms.

All tests make real HTTP calls to the Macroalgae Portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_Macroalgae.py::TestMacroalgaeContract -v
"""

import pytest

from scripts.APIs.Macroalgae import get_macroalgae_synonyms
from tests.APIs.API_Contract_Tests import ApiContractTests


class TestMacroalgaeContract(ApiContractTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_macroalgae_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Ulva lactuca"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Ulva ranunculata"
