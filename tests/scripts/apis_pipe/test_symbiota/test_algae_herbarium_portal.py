"""Unit tests for the Algae Herbarium Portal Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestAlgaeHerbariumPortal(BaseSymbiotaApiTest):
    slug = "algae_herbarium_portal"
    portal_name = "Algae Herbarium Portal"
    expected_accepted_genus = "Ulva"
    expected_accepted_species = "intestinalis"
