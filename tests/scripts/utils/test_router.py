"""
Tests for scripts/utils/router.py

GBIFAPI is mocked so no network calls are made. Tests verify that TaxonRouter
maps kingdoms to the correct API lists and handles failure cases gracefully.

Run from the project root:
    pytest tests/scripts/utils/test_router.py -v
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.utils.router import (
    ANIMALIA_APIS,
    FUNGI_APIS,
    PLANTAE_APIS,
    TaxonRouter,
)


def _make_kingdom_df(kingdom: str) -> pd.DataFrame:
    """Return a one-row DataFrame with the given kingdom value."""
    return pd.DataFrame([{"kingdom": kingdom}])


@pytest.fixture
def mock_gbif():
    """Patch GBIFAPI so TaxonRouter never makes real network calls."""
    with patch("scripts.utils.router.GBIFAPI") as MockGBIF:
        mock_instance = MagicMock()
        MockGBIF.return_value = mock_instance
        yield mock_instance


class TestTaxonRouterRouting:
    def test_animalia_returns_animalia_apis(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = _make_kingdom_df("Animalia")
        router = TaxonRouter()
        assert router.route("Canis lupus") == ANIMALIA_APIS

    def test_plantae_returns_plantae_apis(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = _make_kingdom_df("Plantae")
        router = TaxonRouter()
        assert router.route("Quercus robur") == PLANTAE_APIS

    def test_fungi_returns_fungi_apis(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = _make_kingdom_df("Fungi")
        router = TaxonRouter()
        assert router.route("Amanita muscaria") == FUNGI_APIS

    def test_unknown_kingdom_returns_empty_list(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = _make_kingdom_df("Bacteria")
        router = TaxonRouter()
        assert router.route("Some bacterium") == []


class TestTaxonRouterFailureCases:
    def test_empty_gbif_response_returns_empty_list(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = pd.DataFrame()
        router = TaxonRouter()
        assert router.route("Unknown species") == []

    def test_gbif_exception_returns_empty_list(self, mock_gbif):
        mock_gbif.get_synonyms.side_effect = Exception("network error")
        router = TaxonRouter()
        assert router.route("Anything") == []

    def test_null_kingdom_in_response_returns_empty_list(self, mock_gbif):
        mock_gbif.get_synonyms.return_value = pd.DataFrame([{"kingdom": None}])
        router = TaxonRouter()
        assert router.route("Some species") == []


class TestTaxonRouterApiLists:
    def test_animalia_apis_contains_gbif(self):
        assert "GBIF" in ANIMALIA_APIS

    def test_plantae_apis_contains_gbif(self):
        assert "GBIF" in PLANTAE_APIS

    def test_fungi_apis_contains_index_fungorum(self):
        assert "Index Fungorum" in FUNGI_APIS

    def test_all_api_lists_are_non_empty(self):
        assert len(ANIMALIA_APIS) > 0
        assert len(PLANTAE_APIS) > 0
        assert len(FUNGI_APIS) > 0
