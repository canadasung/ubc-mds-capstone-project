"""
test_GenBank.py — Contract tests for GenBank.get_genbank_synonyms.

All tests make real calls to the NCBI Entrez API and require ENTREZ_EMAIL
to be set in the .env file.

Run from the home directory:
    pytest tests/APIs/test_GenBank.py::TestGenBankContract -v
"""

import os

import pytest

from scripts.APIs.GenBank import get_genbank_synonyms
from test_API import ApiContractTests

_email = os.environ.get("ENTREZ_EMAIL", "")
requires_email = pytest.mark.skipif(
    not _email or _email == "your_email@example.com",
    reason="ENTREZ_EMAIL not set or is still the placeholder — tests require a real email address",
)

pytestmark = requires_email


class TestGenBankContract(ApiContractTests):
    @pytest.fixture
    def api_fn(self):
        return get_genbank_synonyms

    @pytest.fixture
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
