"""Unit tests for the CCH2 Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestCCH2(BaseSymbiotaApiTest):
    slug = "cch2"
    portal_name = "CCH2"
    expected_accepted_genus = "Heteromeles"
    expected_accepted_species = "arbutifolia"
