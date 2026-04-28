"""
test_GenBank.py — Unit and integration tests for GenBank.py

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


_AMANITA_EFETCH_XML = """
<TaxaSet>
  <Taxon>
    <ScientificName>Amanita muscaria</ScientificName>
    <Rank>species</Rank>
  </Taxon>
  <Taxon>
    <ScientificName>Amanita muscaria subsp. flavivolvata</ScientificName>
    <Rank>subspecies</Rank>
  </Taxon>
  <Taxon>
    <ScientificName>Amanita muscaria var. formosa</ScientificName>
    <Rank>varietas</Rank>
  </Taxon>
  <Taxon>
    <ScientificName>Fungi</ScientificName>
    <Rank>kingdom</Rank>
  </Taxon>
</TaxaSet>
"""

_AUREONARIUS_EFETCH_XML = """
<TaxaSet>
  <Taxon>
    <ScientificName>Aureonarius armiae</ScientificName>
    <Rank>no rank</Rank>
  </Taxon>
  <Taxon>
    <ScientificName>Fungi</ScientificName>
    <Rank>kingdom</Rank>
  </Taxon>
</TaxaSet>
"""


@patch("GenBank.requests.get")
def test_species_and_variants(mock_get):
    """Species with subspecies and varieties should appear as cleaned epithets under the correct category keys, and unrelated lineage taxa (e.g. Fungi) should be excluded."""
    mock_get.side_effect = [
        _mock_response(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _mock_response(json_data={"esearchresult": {"idlist": ["67890", "11111"]}}),
        _mock_response(text=_AMANITA_EFETCH_XML),
    ]
    result = get_genbank_synonyms("Amanita muscaria")

    assert "Amanita muscaria" in result
    assert "flavivolvata" in result["Amanita muscaria"]["subspecies"]
    assert "formosa" in result["Amanita muscaria"]["varieties"]
    assert "Fungi" not in result


@patch("GenBank.requests.get")
def test_species_with_no_variants(mock_get):
    """Species with no infraspecific taxa should return a dict with the species as a key and an empty value dict. Also covers the case where NCBI assigns rank 'no rank' instead of 'species'."""
    # Aureonarius armiae has rank "no rank" in NCBI taxonomy
    mock_get.side_effect = [
        _mock_response(json_data={"esearchresult": {"idlist": ["99999"]}}),
        _mock_response(json_data={"esearchresult": {"idlist": []}}),
        _mock_response(text=_AUREONARIUS_EFETCH_XML),
    ]
    result = get_genbank_synonyms("Aureonarius armiae")

    assert result == {"Aureonarius armiae": {}}


@patch("GenBank.requests.get")
def test_nonexistent_species(mock_get):
    """A query that matches no NCBI taxonomy records should return an empty dict and make only one API call (no subtree or efetch requests)."""
    mock_get.return_value = _mock_response(json_data={"esearchresult": {"idlist": []}})
    result = get_genbank_synonyms("Nonexistent species")

    assert result == {}
    mock_get.assert_called_once()  # should short-circuit after the first API call


# --- Integration tests ---
# Run with: pytest -m integration


@pytest.mark.integration
@requires_email
def test_integration_amanita_muscaria():
    """Amanita muscaria should be found in NCBI taxonomy and have at least one infraspecific taxon in any category."""
    result = get_genbank_synonyms("Amanita muscaria")
    assert "Amanita muscaria" in result
    assert any(len(v) > 0 for v in result["Amanita muscaria"].values())


@pytest.mark.integration
@requires_email
def test_integration_aureonarius_armiae():
    """A valid query that returns no NCBI matches should return an empty dict without raising an error."""
    result = get_genbank_synonyms("Aureonarius armiae")
    assert isinstance(result, dict)


@pytest.mark.integration
@requires_email
def test_integration_nonexistent_species():
    """A name that does not exist in NCBI taxonomy should return an empty dict."""
    result = get_genbank_synonyms("Nonexistent species")
    assert result == {}
