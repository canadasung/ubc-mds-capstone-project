"""Unit tests for the Bryophyte Portal Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestBryophytePortal(BaseSymbiotaApiTest):
    slug = "bryophyte_portal"
    portal_name = "Bryophyte Portal"
    expected_accepted_genus = "Pohlia"
    expected_accepted_species = "nutans"
