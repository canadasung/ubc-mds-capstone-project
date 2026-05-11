"""
test_Macroalgae.py — Contract tests for Macroalgae.get_macroalgae_synonyms.

All tests make real HTTP calls to the Macroalgae Portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_Macroalgae.py::TestMacroalgaeContract -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from Macroalgae import get_macroalgae_synonyms
from test_API import ApiContractTests


class TestMacroalgaeContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_macroalgae_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Ulva lactuca"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Ulva ranunculata"

    def test_synonym_query_includes_accepted_name(self):
        """Querying with a synonym name must include the accepted name in the result."""
        result = get_macroalgae_synonyms("Phyllona lactuca")
        assert "Ulva lactuca" in result, (
            f"Expected 'Ulva lactuca' (accepted name) in result for "
            f"'Phyllona lactuca' query, got: {list(result.keys())}"
        )
