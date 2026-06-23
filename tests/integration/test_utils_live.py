"""
test_utils_live.py — Live integration tests for scripts/utils/fuzzy_search.py
and scripts/utils/router.py.

Each test makes real network calls to GBIF to verify end-to-end behaviour,
including graceful handling of nonsense inputs. No mocking is used.

NOTE: These tests require internet access and will fail if the machine is offline.

Run from the project root:
    pytest tests/integration/test_utils_live.py -v
"""

import pytest

from scripts.utils.fuzzy_search import fuzzy_search
from scripts.utils.router import FUNGI_APIS, TaxonRouter

_TEST_FUNGUS = "Amanita muscaria"
_TEST_FUNGUS_MISSPELLED = "Amanita muscara"
_NONSENSE = "xyzzy gibberish1234"


# ---------------------------------------------------------------------------
# fuzzy_search
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fuzzy_search_exact_match():
    """
    Verify that an exact species name returns a list containing that name.

    Calls the real GBIF species/match and species/suggest endpoints.
    """
    result = fuzzy_search(_TEST_FUNGUS)
    assert isinstance(result, list)
    assert _TEST_FUNGUS in result, (
        f"Expected {_TEST_FUNGUS!r} in fuzzy_search result, got {result!r}"
    )


@pytest.mark.integration
def test_fuzzy_search_misspelling_returns_suggestions():
    """
    Verify that a misspelled name returns a non-empty list of suggestions.

    GBIF's fuzzy matching or suggest endpoint should surface candidates even
    for common misspellings.
    """
    result = fuzzy_search(_TEST_FUNGUS_MISSPELLED)
    assert isinstance(result, list)
    assert len(result) > 0, (
        f"Expected at least one suggestion for {_TEST_FUNGUS_MISSPELLED!r}, got empty list"
    )


@pytest.mark.integration
def test_fuzzy_search_nonsense_returns_empty_list():
    """
    Verify that a nonsense query returns an empty list rather than raising.

    Tests graceful handling of bad input — the pipeline should degrade cleanly
    when no match or suggestions exist.
    """
    result = fuzzy_search(_NONSENSE)
    assert result == [], (
        f"Expected [] for nonsense query {_NONSENSE!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# TaxonRouter
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_taxon_router_known_fungus():
    """
    Verify that a known fungus name routes to the Fungi API list.

    Calls the real GBIF backbone to look up the kingdom, then checks that the
    returned list includes the expected fungal databases.
    """
    router = TaxonRouter()
    result = router.route(_TEST_FUNGUS)
    assert isinstance(result, list)
    assert len(result) > 0, (
        f"Expected non-empty API list for {_TEST_FUNGUS!r}, got []"
    )
    assert "GBIF" in result, f"Expected 'GBIF' in result, got {result!r}"
    assert "Index Fungorum" in result, (
        f"Expected 'Index Fungorum' in result, got {result!r}"
    )


@pytest.mark.integration
def test_taxon_router_nonsense_returns_empty_list():
    """
    Verify that a nonsense name returns an empty list rather than raising.

    GBIF will return no match for a made-up name, so the kingdom will be
    unknown and the router should return [] gracefully.
    """
    router = TaxonRouter()
    result = router.route(_NONSENSE)
    assert result == [], (
        f"Expected [] for nonsense query {_NONSENSE!r}, got {result!r}"
    )
