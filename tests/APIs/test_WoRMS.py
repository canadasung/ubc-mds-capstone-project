"""
test_WoRMS.py — Contract tests for WoRMS.get_worms_synonyms.

All tests make real HTTP calls to the WoRMS REST API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_WoRMS.py::TestWoRMSContract -v
"""

import pytest

from scripts.APIs.WoRMS import get_worms_synonyms
from tests.APIs.template_ApiTests import ApiTests


class TestWoRMSContract(ApiTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_worms_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        # Macrocystis pyrifera has 15 species-level synonyms in WoRMS,
        # verified in notebooks/APIs/WoRMS.ipynb
        return "Macrocystis pyrifera"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        # Posidonia australis is an accepted seagrass in WoRMS with no species-level
        # synonyms (confirmed via AphiaSynonymsByAphiaID returning 0 species-rank records)
        return "Posidonia australis"
