"""Unit tests for the MycoBank API client."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.apis_pipe.mycobank import MycoBankAPI
from tests.scripts.apis_pipe._base_api_test import BaseApiTest

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "mycobank"


@pytest.fixture(autouse=True)
def _mycobank_credentials(monkeypatch):
    """Provide dummy credentials so MycoBankAPI() does not raise at construction time."""
    monkeypatch.setenv("MYCOBANK_EMAIL", "test@example.com")
    monkeypatch.setenv("MYCOBANK_PASSWORD", "dummy")


class TestMycoBank(BaseApiTest):
    api_class = MycoBankAPI
    fixture_key = "mycobank"
    expected_accepted_genus = "Amanita"
    expected_accepted_species = "muscaria"


class TestMycoBankCredentials:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("MYCOBANK_EMAIL", raising=False)
        monkeypatch.delenv("MYCOBANK_PASSWORD", raising=False)
        with pytest.raises(ValueError):
            MycoBankAPI()

    def test_missing_password_raises(self, monkeypatch):
        monkeypatch.setenv("MYCOBANK_EMAIL", "test@example.com")
        monkeypatch.delenv("MYCOBANK_PASSWORD", raising=False)
        with pytest.raises(ValueError):
            MycoBankAPI()


class TestMycoBankExtractPublicationYear:
    @pytest.fixture
    def client(self):
        return MycoBankAPI()

    def test_year_present(self, client):
        assert client._extract_publication_year({"yearOfEffectivePublication": "1783"}) == "1783"

    def test_year_absent(self, client):
        assert client._extract_publication_year({}) == ""

    def test_year_none(self, client):
        assert client._extract_publication_year({"yearOfEffectivePublication": None}) == ""


class TestMycoBankExtractPublicationName:
    @pytest.fixture
    def client(self):
        return MycoBankAPI()

    def test_resolved_bibliography(self, client):
        record = {
            "bibliographyinfo": [
                {"id": 7099, "name": "Lamarck, J.B.A.P. de. 1783. Encyclopédie Méthodique."}
            ]
        }
        assert (
            client._extract_publication_name(record)
            == "Lamarck, J.B.A.P. de. 1783. Encyclopédie Méthodique."
        )

    def test_unresolved_bibliography_returns_empty(self, client):
        # application/json mode gives bare ids, not resolved objects.
        assert client._extract_publication_name({"bibliographyinfo": [7099]}) == ""

    def test_empty_bibliography_returns_empty(self, client):
        assert client._extract_publication_name({"bibliographyinfo": []}) == ""

    def test_missing_bibliography_returns_empty(self, client):
        assert client._extract_publication_name({}) == ""


class TestMycoBankExtractTaxonomy:
    @pytest.fixture
    def client(self):
        return MycoBankAPI()

    def test_standard_ranks(self, client):
        data = {
            "classification": [
                {"rank": "regn.", "name": "Fungi"},
                {"rank": "div.", "name": "Basidiomycota"},
                {"rank": "cl.", "name": "Agaricomycetes"},
                {"rank": "ordo", "name": "Agaricales"},
                {"rank": "fam.", "name": "Amanitaceae"},
                {"rank": "subordo", "name": "Pluteineae"},
                {"rank": "gen.", "name": "Amanita"},
            ]
        }
        taxonomy = client._extract_taxonomy(data)
        assert taxonomy == {
            "kingdom": "Fungi",
            "phylum": "Basidiomycota",
            "class_": "Agaricomycetes",
            "order": "Agaricales",
            "family": "Amanitaceae",
        }

    def test_missing_classification_returns_empty_dict(self, client):
        assert client._extract_taxonomy({}) == {}

    def test_subfamily_when_present(self, client):
        data = {"classification": [{"rank": "subfam.", "name": "Amanitoideae"}]}
        assert client._extract_taxonomy(data) == {"subfamily": "Amanitoideae"}


class TestMycoBankFetchSynonymData:
    @pytest.fixture
    def client(self):
        return MycoBankAPI()

    def test_collects_ids_from_all_synonym_groups(self, client):
        raw_data = {
            "id": 1133,
            "synonymy": {
                "currentName": {"id": 1133},
                "taxonSynonyms": [{"id": 125058}, {"id": 207642}],
                "obligateSynonyms": [{"id": 194377}],
                "basionym": {"id": 194378},
            },
        }
        with patch.object(client, "_authed_get", return_value={"id": 0, "name": "x"}) as mock_get:
            result = client._fetch_synonym_data(raw_data)
        called_ids = [call.args[0] for call in mock_get.call_args_list]
        assert called_ids == [
            "/taxonnames/125058",
            "/taxonnames/207642",
            "/taxonnames/194377",
            "/taxonnames/194378",
        ]
        assert len(result) == 4

    def test_skips_own_id_and_duplicates(self, client):
        raw_data = {
            "id": 1133,
            "synonymy": {
                "currentName": {"id": 1133},
                "taxonSynonyms": [{"id": 1133}, {"id": 125058}, {"id": 125058}],
                "obligateSynonyms": [],
                "basionym": None,
            },
        }
        with patch.object(client, "_authed_get", return_value={"id": 125058, "name": "x"}) as mock_get:
            result = client._fetch_synonym_data(raw_data)
        assert mock_get.call_count == 1
        assert len(result) == 1

    def test_skips_synonym_that_fails_to_resolve(self, client):
        import requests

        raw_data = {
            "id": 1133,
            "synonymy": {
                "currentName": {"id": 1133},
                "taxonSynonyms": [{"id": 125058}],
                "obligateSynonyms": [],
                "basionym": None,
            },
        }
        with patch.object(client, "_authed_get", side_effect=requests.RequestException("boom")):
            result = client._fetch_synonym_data(raw_data)
        assert result == []

    def test_own_id_in_synonym_group_uses_raw_data_without_extra_fetch(self, client):
        # Regression test: when the queried record is itself a synonym, the
        # API returns the whole group's synonymy, which includes the queried
        # record's own id. It must be resolved from raw_data directly (not
        # skipped), since raw_data already has a clean, resolved name.
        raw_data = {
            "id": 125058,
            "name": "Amanita chrysoblema",
            "synonymy": {
                "currentName": {"id": 1133},
                "taxonSynonyms": [{"id": 125058}, {"id": 207642}],
                "obligateSynonyms": [],
                "basionym": None,
            },
        }
        with patch.object(client, "_authed_get", return_value={"id": 207642, "name": "y"}) as mock_get:
            result = client._fetch_synonym_data(raw_data)
        called_ids = [call.args[0] for call in mock_get.call_args_list]
        assert called_ids == ["/taxonnames/207642"]
        assert raw_data in result
        assert len(result) == 2

    def test_accepted_name_id_in_synonym_group_is_excluded(self, client):
        # The accepted name's own id should never appear as a synonym row,
        # even if it were present in the raw synonym-group data.
        raw_data = {
            "id": 125058,
            "synonymy": {
                "currentName": {"id": 1133},
                "taxonSynonyms": [{"id": 1133}, {"id": 207642}],
                "obligateSynonyms": [],
                "basionym": None,
            },
        }
        with patch.object(client, "_authed_get", return_value={"id": 207642, "name": "y"}) as mock_get:
            result = client._fetch_synonym_data(raw_data)
        called_ids = [call.args[0] for call in mock_get.call_args_list]
        assert called_ids == ["/taxonnames/207642"]
        assert len(result) == 1

    def test_real_synonym_fixture_includes_the_searched_name_itself(self, client):
        # End-to-end regression test against the real recorded API response
        # for querying "Amanita chrysoblema" (a synonym). Only the network
        # layer (_authed_get) is mocked; _fetch_synonym_data runs for real.
        raw_data = json.loads(
            (_FIXTURES_DIR / "synonym" / "query_data.json").read_text(encoding="utf-8")
        )
        assert raw_data["id"] == 125058
        assert raw_data["name"] == "Amanita chrysoblema"

        with patch.object(client, "_authed_get", return_value={}):
            result = client._fetch_synonym_data(raw_data)

        assert raw_data in result, (
            "Expected the queried record itself to be resolved into the "
            "synonym list, since its own id appears in its own "
            "synonymy.taxonSynonyms in the real API response"
        )


class TestMycoBankFetchAcceptedData:
    @pytest.fixture
    def client(self):
        return MycoBankAPI()

    def test_fast_path_when_query_is_accepted(self, client):
        raw_data = {"id": 1133, "synonymy": {"currentName": {"id": 1133}}}
        with patch.object(client, "_authed_get") as mock_get:
            result = client._fetch_accepted_data(raw_data, [])
        mock_get.assert_not_called()
        assert result is raw_data

    def test_slow_path_when_query_is_synonym(self, client):
        raw_data = {"id": 125058, "synonymy": {"currentName": {"id": 1133}}}
        accepted_record = {"id": 1133, "name": "Amanita muscaria"}
        with patch.object(client, "_authed_get", return_value=accepted_record) as mock_get:
            result = client._fetch_accepted_data(raw_data, [])
        mock_get.assert_called_once_with(
            "/taxonnames/1133",
            params={"include": client._ACCEPTED_INCLUDE},
            accept="application/links+json",
        )
        assert result == accepted_record
