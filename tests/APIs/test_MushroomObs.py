"""
test_MushroomObs.py — Contract tests for MushroomObs.get_mushroom_observer_synonyms.

All tests make real calls to the MushroomObserver API (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_MushroomObs.py::TestMushroomObsContract -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from MushroomObs import get_mushroom_observer_synonyms
from test_API import ApiContractTests


class TestMushroomObsContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_mushroom_observer_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
