"""Unit tests for the MyCoPortal Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestMyCoPortal(BaseSymbiotaApiTest):
    slug = "mycoportal"
    portal_name = "MyCoPortal"
    expected_accepted_genus = "Agaricus"
    expected_accepted_species = "campestris"
