"""
test_MyCoPortal.py — Contract tests for MyCoPortal.get_mycoportal_synonyms.

All tests make real HTTP calls to the MyCoPortal portal (no authentication required).

Run from the home directory:
    pytest tests/APIs/test_MyCoPortal.py::TestMyCoPortalContract -v
"""

import pytest

from deprecated.scripts_APIs.MyCoPortal import get_mycoportal_synonyms
from tests.APIs.template_ApiTests import ApiTests


class TestMyCoPortalContract(ApiTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_mycoportal_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Gymnopus dryophilus"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Amanita muscaria"
