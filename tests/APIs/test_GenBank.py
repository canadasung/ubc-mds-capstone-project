"""
test_GenBank.py — Contract tests for GenBank.get_genbank_synonyms.

All tests make real calls to the NCBI Entrez API and require ENTREZ_EMAIL
to be set in the .env file.

Run from the home directory:
    pytest tests/APIs/test_GenBank.py::TestGenBankContract -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from GenBank import get_genbank_synonyms
from test_API import ApiContractTests

requires_email = pytest.mark.skipif(
    not os.environ.get("ENTREZ_EMAIL"),
    reason="ENTREZ_EMAIL not set — tests require a configured .env file",
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
