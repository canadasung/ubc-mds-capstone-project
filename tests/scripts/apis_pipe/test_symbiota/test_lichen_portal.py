"""Unit tests for the Lichen Portal Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestLichenPortal(BaseSymbiotaApiTest):
    slug = "lichen_portal"
    portal_name = "Lichen Portal"
    expected_accepted_genus = "Xanthoria"
    expected_accepted_species = "parietina"
