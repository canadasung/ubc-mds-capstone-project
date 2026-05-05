"""
test_BryophytePortal.py — Contract tests for BryophytePortal.get_bryophyteportal_synonyms.

All tests make real HTTP calls to the BryophytePortal portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_BryophytePortal.py::TestBryophytePortalContract -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from BryophytePortal import get_bryophyteportal_synonyms
from test_API import ApiContractTests


class TestBryophytePortalContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_bryophyteportal_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Marchantia polymorpha"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Fissidens aphelotaxifolius"
