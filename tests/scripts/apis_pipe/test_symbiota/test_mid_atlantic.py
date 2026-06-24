"""Unit tests for the Mid-Atlantic Herbaria Consortium Symbiota client."""

from tests.scripts.apis_pipe._symbiota_api_test import BaseSymbiotaApiTest


class TestMidAtlantic(BaseSymbiotaApiTest):
    slug = "mid_atlantic"
    portal_name = "Mid-Atlantic Herbaria Consortium"
    expected_accepted_genus = "Quercus"
    expected_accepted_species = "rubra"
