"""
test_MyCoPortal.py — Contract tests for MyCoPortal.get_mycoportal_synonyms.

All tests make real HTTP calls to the MyCoPortal portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_MyCoPortal.py::TestMyCoPortalContract -v
"""

import pytest
from test_API import ApiContractTests

from scripts.APIs.MyCoPortal import get_mycoportal_synonyms


class TestMyCoPortalContract(ApiContractTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_mycoportal_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Gymnopus dryophilus"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Amanita muscaria"

    def test_synonym_query_includes_accepted_name(self):
        """Querying with a synonym name must include the accepted name in the result."""
        result = get_mycoportal_synonyms("Agaricus dryophilus")
        assert "Gymnopus dryophilus" in result, (
            f"Expected 'Gymnopus dryophilus' (accepted name) in result for "
            f"'Agaricus dryophilus' query, got: {list(result.keys())}"
        )
