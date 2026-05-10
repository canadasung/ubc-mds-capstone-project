"""
test_IndexFungorum.py — Contract tests for IndexFungorum.get_indexfungorum_synonyms.

All tests make real HTTP calls to the Index Fungorum web service (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_IndexFungorum.py::TestIndexFungorumContract -v
"""

import pytest

from scripts.APIs.IndexFungorum import get_indexfungorum_synonyms
from test_API import ApiContractTests


class TestIndexFungorumContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_indexfungorum_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"