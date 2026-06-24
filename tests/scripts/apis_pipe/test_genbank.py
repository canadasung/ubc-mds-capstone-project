"""Unit tests for the GenBank API client."""

import xml.etree.ElementTree as ET

import pytest

from scripts.apis_pipe.genbank import GenBankAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestGenBank(BaseApiTest):
    api_class = GenBankAPI
    fixture_key = "genbank"
    expected_accepted_genus = "Amanita"
    expected_accepted_species = "muscaria"


@pytest.fixture
def client():
    return GenBankAPI()


class TestGenBankExtractPublicationYear:
    def test_trailing_year(self, client):
        assert client._extract_publication_year("Amanita muscaria (L.) Lam., 1783") == "1783"

    def test_no_year_returns_empty(self, client):
        assert client._extract_publication_year("Amanita muscaria") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_year("") == ""


class TestGenBankExtractAuthor:
    def test_author_with_parenthetical(self, client):
        assert client._extract_author("Amanita muscaria (L.) Lam., 1783") == "(L.) Lam."

    def test_simple_author(self, client):
        assert client._extract_author("Agaricus muscarius L., 1753") == "L."

    def test_no_match_returns_empty(self, client):
        assert client._extract_author("Amanita muscaria") == ""

    def test_empty_string_returns_empty(self, client):
        assert client._extract_author("") == ""


class TestGenBankFindAuthorityDispName:
    def _make_other_names(self, entries: list[tuple[str, str]]) -> ET.Element:
        """Build an OtherNames element from (ClassCDE, DispName) pairs."""
        other_names = ET.Element("OtherNames")
        for cde, disp in entries:
            name_el = ET.SubElement(other_names, "Name")
            ET.SubElement(name_el, "ClassCDE").text = cde
            ET.SubElement(name_el, "DispName").text = disp
        return other_names

    def test_finds_matching_authority_entry(self, client):
        other_names = self._make_other_names([
            ("authority", "Amanita muscaria (L.) Lam., 1783"),
            ("authority", "Agaricus muscarius L., 1753"),
        ])
        result = client._find_authority_disp_name(other_names, "Amanita muscaria")
        assert result == "Amanita muscaria (L.) Lam., 1783"

    def test_non_authority_entry_ignored(self, client):
        other_names = self._make_other_names([
            ("synonym", "Amanita muscaria (L.) Lam., 1783"),
        ])
        result = client._find_authority_disp_name(other_names, "Amanita muscaria")
        assert result == ""

    def test_no_match_returns_empty(self, client):
        other_names = self._make_other_names([
            ("authority", "Gadus morhua L., 1758"),
        ])
        result = client._find_authority_disp_name(other_names, "Amanita muscaria")
        assert result == ""

    def test_empty_other_names_returns_empty(self, client):
        other_names = ET.Element("OtherNames")
        result = client._find_authority_disp_name(other_names, "Amanita muscaria")
        assert result == ""
