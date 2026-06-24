"""Unit tests for the Pterido Portal Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestPteridoPortal(BaseSymbiotaApiTest):
    slug = "pterido_portal"
    portal_name = "Pterido Portal"
    expected_accepted_genus = "Dryopteris"
    expected_accepted_species = "filix-mas"
