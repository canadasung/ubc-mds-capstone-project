"""Unit tests for the SERNEC Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestSERNEC(BaseSymbiotaApiTest):
    slug = "sernec"
    portal_name = "SERNEC"
    expected_accepted_genus = "Magnolia"
    expected_accepted_species = "grandiflora"
