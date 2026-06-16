"""
test_BryophytePortal.py — Contract tests for BryophytePortal.get_bryophyteportal_synonyms.

All tests make real HTTP calls to the BryophytePortal portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_BryophytePortal.py::TestBryophytePortalContract -v
"""

import pytest

from deprecated.scripts_APIs.BryophytePortal import get_bryophyteportal_synonyms
from tests.APIs.template_ApiTests import ApiTests


class TestBryophytePortalContract(ApiTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_bryophyteportal_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Marchantia polymorpha"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Fissidens aphelotaxifolius"
