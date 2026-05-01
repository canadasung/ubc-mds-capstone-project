"""
test_GenBank.py — Unit and integration tests for GenBank.py

Tests the current behaviour of get_genbank_synonyms, which returns a dict
whose keys are the queried species name plus all NCBI species-level synonyms,
and whose values are empty lists (placeholders for rank categories, in-progress).

Unit tests mock all NCBI API calls and run without network access.
Integration tests make real calls to the NCBI Entrez API and require
ENTREZ_EMAIL to be set in the .env file.

Run from the tests/ directory:

    # Unit tests only (fast, no network)
    pytest APIs/test_GenBank.py -v -m "not integration"

    # Integration tests only (requires network and ENTREZ_EMAIL)
    pytest APIs/test_GenBank.py -v -m integration

    # All tests
    pytest APIs/test_GenBank.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "APIs"))
from GenBank import get_genbank_synonyms

requires_email = pytest.mark.skipif(
    not os.environ.get("ENTREZ_EMAIL"),
    reason="ENTREZ_EMAIL not set — integration tests require a configured .env file",
)


def _mock_response(json_data=None, text=""):
    """Build a mock requests.Response with a given JSON payload or text body."""
    m = MagicMock()
    m.json.return_value = json_data or {}
    m.text = text
    return m


# --- XML fixtures ---

_AMANITA_WITH_SYNONYM_XML = """
<TaxaSet>
  <Taxon>
    <ScientificName>Amanita muscaria</ScientificName>
    <Rank>species</Rank>
    <OtherNames>
      <Synonym>Agaricus muscarius</Synonym>
    </OtherNames>
  </Taxon>
</TaxaSet>
"""

_AGARICUS_WITH_SYNONYM_XML = """
<TaxaSet>
  <Taxon>
    <ScientificName>Agaricus muscarius</ScientificName>
    <Rank>species</Rank>
    <OtherNames>
      <Synonym>Amanita muscaria</Synonym>
    </OtherNames>
  </Taxon>
</TaxaSet>
"""

_NO_SYNONYMS_XML = """
<TaxaSet>
  <Taxon>
    <ScientificName>Aureonarius armiae</ScientificName>
    <Rank>no rank</Rank>
  </Taxon>
</TaxaSet>
"""

# --- Unit tests ---


@patch("GenBank.requests.get")
@patch("GenBank.time.sleep")
def test_returns_query_and_synonyms(_, mock_get):
    """Species with a synonym should return both names as keys with empty list values."""
    mock_get.side_effect = [
        # Loop 1: esearch + efetch for primary record
        _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _mock_response(text=_AMANITA_WITH_SYNONYM_XML),
        # Loop 2, "Amanita muscaria": esearch + efetch
        _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _mock_response(text=_AMANITA_WITH_SYNONYM_XML),
        # Loop 2, "Agaricus muscarius": esearch + efetch
        _mock_response(json_data={"esearchresult": {"idlist": ["67890"]}}),
        _mock_response(text=_AGARICUS_WITH_SYNONYM_XML),
    ]
    result = get_genbank_synonyms("Amanita muscaria")

    assert "Amanita muscaria" in result
    assert "Agaricus muscarius" in result
    assert result["Amanita muscaria"] == []
    assert result["Agaricus muscarius"] == []


@patch("GenBank.requests.get")
@patch("GenBank.time.sleep")
def test_circular_synonyms_not_duplicated(_, mock_get):
    """Circular synonym chains (A→B, B→A) should not produce duplicate entries."""
    mock_get.side_effect = [
        _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _mock_response(text=_AMANITA_WITH_SYNONYM_XML),
        _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _mock_response(text=_AMANITA_WITH_SYNONYM_XML),
        _mock_response(json_data={"esearchresult": {"idlist": ["67890"]}}),
        _mock_response(text=_AGARICUS_WITH_SYNONYM_XML),
    ]
    result = get_genbank_synonyms("Amanita muscaria")

    assert list(result.keys()).count("Amanita muscaria") == 1
    assert list(result.keys()).count("Agaricus muscarius") == 1


@patch("GenBank.requests.get")
@patch("GenBank.time.sleep")
def test_no_synonyms(_, mock_get):
    """Species with no OtherNames block should return only the query name."""
    mock_get.side_effect = [
        # Loop 1
        _mock_response(json_data={"esearchresult": {"idlist": ["99999"]}}),
        _mock_response(text=_NO_SYNONYMS_XML),
        # Loop 2, only the query itself
        _mock_response(json_data={"esearchresult": {"idlist": ["99999"]}}),
        _mock_response(text=_NO_SYNONYMS_XML),
    ]
    result = get_genbank_synonyms("Aureonarius armiae")

    assert result == {"Aureonarius armiae": []}


@patch("GenBank.requests.get")
@patch("GenBank.time.sleep")
def test_nonexistent_species(_, mock_get):
    """A query that matches no NCBI records should return an empty dict after one API call."""
    mock_get.return_value = _mock_response(json_data={"esearchresult": {"idlist": []}})
    result = get_genbank_synonyms("Nonexistent species")

    assert result == {}
    mock_get.assert_called_once()


# --- Commented out: old tests for rank categories (in-progress) ---

# @patch("GenBank.requests.get")
# def test_species_and_variants(mock_get):
#     """Species with subspecies and varieties should appear as cleaned epithets
#     under the correct category keys, and unrelated lineage taxa (e.g. Fungi)
#     should be excluded."""
#     mock_get.side_effect = [
#         _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
#         _mock_response(json_data={"esearchresult": {"idlist": ["67890", "11111"]}}),
#         _mock_response(text=_AMANITA_EFETCH_XML),
#     ]
#     result = get_genbank_synonyms("Amanita muscaria")
#     assert "Amanita muscaria" in result
#     assert "flavivolvata" in result["Amanita muscaria"]["subspecies"]
#     assert "formosa" in result["Amanita muscaria"]["varieties"]
#     assert "Fungi" not in result

# @patch("GenBank.requests.get")
# def test_species_with_no_variants(mock_get):
#     """Species with no infraspecific taxa should return a dict with the species
#     as a key and an empty value dict."""
#     mock_get.side_effect = [
#         _mock_response(json_data={"esearchresult": {"idlist": ["99999"]}}),
#         _mock_response(json_data={"esearchresult": {"idlist": []}}),
#         _mock_response(text=_AUREONARIUS_EFETCH_XML),
#     ]
#     result = get_genbank_synonyms("Aureonarius armiae")
#     assert result == {"Aureonarius armiae": {}}


# --- Integration tests ---
# Run with: pytest -m integration


@pytest.mark.integration
@requires_email
def test_integration_amanita_muscaria():
    """Amanita muscaria should be found in NCBI and return at least one synonym."""
    result = get_genbank_synonyms("Amanita muscaria")
    assert isinstance(result, dict)
    assert len(result) > 1


@pytest.mark.integration
@requires_email
def test_integration_all_values_are_empty_lists():
    """All values in the result should be empty lists (rank categories not yet populated)."""
    result = get_genbank_synonyms("Amanita muscaria")
    assert all(v == [] for v in result.values())


@pytest.mark.integration
@requires_email
def test_integration_aureonarius_armiae():
    """A valid but obscure query should return a dict without raising an error."""
    result = get_genbank_synonyms("Aureonarius armiae")
    assert isinstance(result, dict)


@pytest.mark.integration
@requires_email
def test_integration_nonexistent_species():
    """A name that does not exist in NCBI taxonomy should return an empty dict."""
    result = get_genbank_synonyms("Nonexistent species")
    assert result == {}
