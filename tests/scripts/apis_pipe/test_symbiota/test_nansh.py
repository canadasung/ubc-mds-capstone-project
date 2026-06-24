"""Unit tests for the NANSH Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestNANSH(BaseSymbiotaApiTest):
    slug = "nansh"
    portal_name = "NANSH"
    expected_accepted_genus = "Rudbeckia"
    expected_accepted_species = "hirta"
