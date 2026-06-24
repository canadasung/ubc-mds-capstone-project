"""Unit tests for the swbiodiversity Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestSwbiodiversity(BaseSymbiotaApiTest):
    slug = "swbiodiversity"
    portal_name = "swbiodiversity"
    expected_accepted_genus = "Larrea"
    expected_accepted_species = "tridentata"
