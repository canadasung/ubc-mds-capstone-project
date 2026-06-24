"""
Unit tests for shared utility methods in SpeciesAPI (scripts/apis_pipe/base.py).

Uses a minimal concrete stub subclass to satisfy the abstract interface so that
the shared methods can be exercised in isolation without any network calls.
"""

import xml.etree.ElementTree as ET

import pytest

from scripts.apis_pipe.base import SpeciesAPI
from scripts.utils.schema import SYNONYM_COLUMNS, UNAVAILABLE


class _Stub(SpeciesAPI):
    BASE_URL = "https://example.com"

    def _fetch_query_data(self, name):
        return {}

    def _fetch_synonym_data(self, raw_data):
        return {}

    def _fetch_accepted_data(self, raw_data, synonym_data):
        return {}

    def _compile_synonyms(self, synonym_data):
        return []

    def _compile_accepted(self, accepted_data):
        return []


@pytest.fixture
def client():
    return _Stub()


class TestIsEmpty:
    def test_empty_dict(self, client):
        assert client._is_empty({}) is True

    def test_empty_list(self, client):
        assert client._is_empty([]) is True

    def test_empty_string(self, client):
        assert client._is_empty("") is True

    def test_none(self, client):
        assert client._is_empty(None) is True

    def test_empty_element(self, client):
        assert client._is_empty(ET.Element("empty")) is True

    def test_nonempty_dict(self, client):
        assert client._is_empty({"key": "value"}) is False

    def test_nonempty_list(self, client):
        assert client._is_empty(["a"]) is False

    def test_nonempty_string(self, client):
        assert client._is_empty("text") is False

    def test_nonempty_element(self, client):
        parent = ET.Element("root")
        ET.SubElement(parent, "child")
        assert client._is_empty(parent) is False


class TestIsInfraspecific:
    def test_var_marker(self, client):
        assert client._is_infraspecific("Amanita muscaria var. flavivolvata") is True

    def test_subsp_marker(self, client):
        assert client._is_infraspecific("Gadus morhua subsp. morhua") is True

    def test_ssp_marker(self, client):
        assert client._is_infraspecific("Gadus morhua ssp. morhua") is True

    def test_f_marker(self, client):
        assert client._is_infraspecific("Quercus robur f. pendula") is True

    def test_fo_marker(self, client):
        assert client._is_infraspecific("Quercus robur fo. pendula") is True

    def test_subf_marker(self, client):
        assert client._is_infraspecific("Quercus robur subf. pendula") is True

    def test_three_bare_tokens(self, client):
        assert client._is_infraspecific("Gadus morhua morhua") is True

    def test_two_tokens_is_not_infraspecific(self, client):
        assert client._is_infraspecific("Amanita muscaria") is False

    def test_one_token_is_not_infraspecific(self, client):
        assert client._is_infraspecific("Amanita") is False


class TestExtractGenusSpecies:
    def test_two_tokens(self, client):
        assert client._extract_genus_species("Amanita muscaria") == ("Amanita", "muscaria")

    def test_three_tokens_returns_first_two(self, client):
        assert client._extract_genus_species("Amanita muscaria var.") == ("Amanita", "muscaria")

    def test_one_token_raises(self, client):
        with pytest.raises(ValueError):
            client._extract_genus_species("Amanita")


class TestExtractStatus:
    def test_accepted(self, client):
        assert client._extract_status("accepted name") == "Accepted"

    def test_synonym(self, client):
        assert client._extract_status("ambiguous synonym") == "Synonym"

    def test_unknown_returns_empty(self, client):
        assert client._extract_status("unknown") == ""

    def test_case_insensitive(self, client):
        assert client._extract_status("ACCEPTED") == "Accepted"
        assert client._extract_status("SYNONYM") == "Synonym"


class TestFormatRow:
    def test_minimal_required_fields_produces_all_columns(self, client):
        row = client._format_row(
            api_name="GBIF",
            genus="Amanita",
            species="muscaria",
            api_internal_id="12345",
        )
        assert set(row.keys()) == set(SYNONYM_COLUMNS)

    def test_optional_fields_default_to_unavailable(self, client):
        row = client._format_row(
            api_name="GBIF",
            genus="Amanita",
            species="muscaria",
            api_internal_id="12345",
        )
        assert row["kingdom"] == UNAVAILABLE
        assert row["author"] == UNAVAILABLE
        assert row["publication_year"] == UNAVAILABLE

    def test_provided_optional_fields_are_set(self, client):
        row = client._format_row(
            api_name="GBIF",
            genus="Amanita",
            species="muscaria",
            api_internal_id="12345",
            author="(L.) Lam.",
            status="Accepted",
        )
        assert row["author"] == "(L.) Lam."
        assert row["status"] == "Accepted"
