"""
test_MushroomObs.py — Contract tests for MushroomObs.get_mushroom_observer_synonyms.

All tests make real calls to the MushroomObserver API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_MushroomObs.py::TestMushroomObsContract -v
"""

import pytest
from test_API import ApiContractTests

from scripts.APIs.MushroomObs import get_mushroom_observer_synonyms


class TestMushroomObsContract(ApiContractTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_mushroom_observer_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
