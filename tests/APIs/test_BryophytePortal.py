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
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_bryophyteportal_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Marchantia polymorpha"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Fissidens aphelotaxifolius"

    def test_synonym_query_includes_accepted_name(self):
        """Querying with a synonym name must include the accepted name in the result."""
        result = get_bryophyteportal_synonyms("Marchantia alpestris")
        assert "Marchantia polymorpha" in result, (
            f"Expected 'Marchantia polymorpha' (accepted name) in result for "
            f"'Marchantia alpestris' query, got: {list(result.keys())}"
        )
