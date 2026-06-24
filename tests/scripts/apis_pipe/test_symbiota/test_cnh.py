"""Unit tests for the CNH Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestCNH(BaseSymbiotaApiTest):
    slug = "cnh"
    portal_name = "CNH"
    expected_accepted_genus = "Impatiens"
    expected_accepted_species = "capensis"
