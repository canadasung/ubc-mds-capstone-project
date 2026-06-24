"""Unit tests for the Index Fungorum API client."""

from scripts.apis_pipe.index_fungorum import IndexFungorumAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestIndexFungorum(BaseApiTest):
    api_class = IndexFungorumAPI
    fixture_key = "index_fungorum"
    expected_accepted_genus = "Amanita"
    expected_accepted_species = "muscaria"
