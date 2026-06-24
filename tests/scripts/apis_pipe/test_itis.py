"""Unit tests for the ITIS API client."""

import contextlib
from unittest.mock import patch

import pytest

from scripts.apis_pipe.itis import ITISAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class TestITIS(BaseApiTest):
    api_class = ITISAPI
    fixture_key = "itis"
    expected_accepted_genus = "Oncorhynchus"
    expected_accepted_species = "mykiss"

    def _run(self, scenario: str):
        """Override to also patch _fetch_hierarchy_data and, for synonym, _fetch_internal_accepted_id_data."""
        client = self._make_client()
        query_data = self._load(scenario, "query_data")
        synonym_data = self._load_or_none(scenario, "synonym_data")
        accepted_data = self._load_or_none(scenario, "accepted_data")
        hierarchy_data = self._load_or_none(scenario, "hierarchy_data") or []

        patches = [
            patch.object(client, "_fetch_query_data", return_value=query_data),
            patch.object(client, "_fetch_synonym_data", return_value=synonym_data),
            patch.object(client, "_fetch_accepted_data", return_value=accepted_data),
            patch.object(client, "_fetch_hierarchy_data", return_value=hierarchy_data),
        ]

        if scenario == "synonym":
            internal_accepted_id_data = self._load_or_none(scenario, "internal_accepted_id_data") or []
            patches.append(
                patch.object(
                    client,
                    "_fetch_internal_accepted_id_data",
                    return_value=internal_accepted_id_data,
                )
            )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return client.get_synonyms(self._queries()[scenario])


@pytest.fixture
def client():
    return ITISAPI()


class TestITISExtractPublicationYear:
    def test_trailing_year(self, client):
        assert client._extract_publication_year("Walbaum, 1792") == "1792"

    def test_trailing_year_with_leading_author(self, client):
        assert client._extract_publication_year("L., 1753") == "1753"

    def test_string_ending_with_paren_returns_empty(self, client):
        assert client._extract_publication_year("(Rafinesque, 1820)") == ""

    def test_parenthesised_author_returns_empty(self, client):
        assert client._extract_publication_year("(L.) Lam., 1783") == "1783"

    def test_empty_string_returns_empty(self, client):
        assert client._extract_publication_year("") == ""


class TestITISStripLinks:
    def test_strips_anchor_tag_preserving_text(self):
        assert ITISAPI._strip_links('<a href="http://example.com">link text</a>') == "link text"

    def test_strips_bare_url(self):
        result = ITISAPI._strip_links("see https://example.com for details")
        assert "https://example.com" not in result
        assert "see" in result

    def test_plain_text_unchanged(self):
        assert ITISAPI._strip_links("plain text") == "plain text"

    def test_empty_string_unchanged(self):
        assert ITISAPI._strip_links("") == ""


class TestITISExtractOriginalSource:
    def test_publication_formatted_with_year(self, client):
        data = {
            "publicationList": {
                "publications": [
                    {"pubName": "Journal of Science", "actualPubDate": "1900-01-01"}
                ]
            },
            "otherSourceList": {"otherSources": []},
        }
        result = client._extract_original_source(data)
        assert "Journal of Science" in result
        assert "1900" in result

    def test_multiple_sources_sorted_by_year(self, client):
        data = {
            "publicationList": {
                "publications": [
                    {"pubName": "Later Source", "actualPubDate": "1950-01-01"},
                    {"pubName": "Earlier Source", "actualPubDate": "1900-01-01"},
                ]
            },
            "otherSourceList": {"otherSources": []},
        }
        result = client._extract_original_source(data)
        assert result.index("Earlier Source") < result.index("Later Source")

    def test_empty_lists_return_empty_string(self, client):
        data = {"publicationList": {"publications": []}, "otherSourceList": {"otherSources": []}}
        assert client._extract_original_source(data) == ""

    def test_missing_keys_return_empty_string(self, client):
        assert client._extract_original_source({}) == ""
