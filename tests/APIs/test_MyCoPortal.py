"""
test_MyCoPortal.py — Contract tests for MyCoPortal.get_mycoportal_synonyms.

All tests make real HTTP calls to the MyCoPortal portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_MyCoPortal.py::TestMyCoPortalContract -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from MyCoPortal import get_mycoportal_synonyms
from test_API import ApiContractTests


class TestMyCoPortalContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_mycoportal_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Gymnopus dryophilus"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Amanita muscaria"
