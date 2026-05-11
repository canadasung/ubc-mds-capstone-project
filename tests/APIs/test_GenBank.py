"""
test_GenBank.py — Contract tests for GenBank.get_genbank_synonyms.

All tests make real calls to the NCBI Entrez API and require ENTREZ_EMAIL
to be set in the .env file.

Run from the home directory:
    pytest tests/APIs/test_GenBank.py::TestGenBankContract -v
"""

import pytest

from scripts.APIs.GenBank import get_genbank_synonyms
from test_API import ApiContractTests

pytestmark = pytest.mark.usefixtures("require_entrez_email")


class TestGenBankContract(ApiContractTests):
    @pytest.fixture(scope="class")
    def api_fn(self):
        return get_genbank_synonyms

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        return "Amanita muscaria"

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        return "Candelariella antennaria"
