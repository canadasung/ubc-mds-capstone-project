"""
Unit and integration tests for SymbiotaAPI.

Unit tests are fully mocked (no network). Integration tests hit real portals
and are skipped automatically when the network is unavailable.

Run only unit tests:
    pytest tests/APIs/test_symbiota.py -v -m "not integration"

Run only integration tests:
    pytest tests/APIs/test_symbiota.py -v -m integration

Run everything:
    pytest tests/APIs/test_symbiota.py -v
"""

import json
import re
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from scripts.APIs_pipe.symbiota import COLUMNS, SymbiotaAPI

# ── Shared mock data ───────────────────────────────────────────────────────────

_MOCK_SEARCH_RESULTS = {
    "results": [
        {
            "tid": 95084,
            "sciname": "Amanita muscaria",
            "author": "(L.) Lam.",
            "status": "accepted",
        }
    ]
}

_MOCK_TAXONOMY_ACCEPTED = {
    "tid": 95084,
    "kingdomName": "Fungi",
    "scientificName": "Amanita muscaria",
    "author": "(L.) Lam.",
    "status": "accepted",
    "classification": [
        {"rankid": 30,  "scientificName": "Basidiomycota"},
        {"rankid": 60,  "scientificName": "Agaricomycetes"},
        {"rankid": 140, "scientificName": "Amanitaceae"},
    ],
}

_MOCK_TAXONOMY_SYNONYM = {
    "tid": 51234,
    "kingdomName": "Fungi",
    "scientificName": "Agaricus muscarius",
    "author": "L.",
    "status": "synonym",
    "accepted": {
        "tid": 95084,
        "scientificName": "Amanita muscaria",
        "scientificNameAuthorship": "(L.) Lam.",
    },
    "classification": [
        {"rankid": 30,  "scientificName": "Basidiomycota"},
        {"rankid": 60,  "scientificName": "Agaricomycetes"},
        {"rankid": 140, "scientificName": "Amanitaceae"},
    ],
}

# Realistic synonymDiv HTML: two linked synonyms + one infraspecific (must be filtered)
_MOCK_HTML_SYNONYMDIV = """
<html><body>
<div id="synonymDiv">
  <a href="index.php?tid=51234"><i>Agaricus muscarius</i></a> L.,
  <a href="index.php?tid=51235"><i>Amanita aureola</i></a> (Kalchbr.) Sacc.
  <i>Amanita muscaria var. flavivolvata</i> Singer
</div>
</body></html>
"""

# synonymDiv with no <a href> tid links (taxon= style portals)
_MOCK_HTML_NO_TID_LINKS = """
<html><body>
<div id="synonymDiv">
  <i>Agaricus muscarius</i> L.
</div>
</body></html>
"""

_MOCK_HTML_EMPTY_DIV = "<html><body><div id='synonymDiv'></div></body></html>"
_MOCK_HTML_NO_DIV    = "<html><body><p>No synonyms here</p></body></html>"

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


def _mock_resp(json_data=None, text=None, status=200):
    """
    Build a minimal mock requests.Response.

    Parameters
    ----------
    json_data : dict or list, optional
        Value returned by ``response.json()``. Defaults to ``{}``.
    text : str, optional
        Raw response text. Defaults to the JSON-serialized *json_data*.
    status : int, optional
        HTTP status code. Default is 200.

    Returns
    -------
    unittest.mock.MagicMock
        Mock with ``ok``, ``status_code``, ``json``, ``text``, and
        ``raise_for_status`` attributes configured.
    """
    m = MagicMock()
    m.ok = (status < 400)
    m.status_code = status
    m.json.return_value = json_data if json_data is not None else {}
    m.text = text if text is not None else json.dumps(json_data or {})
    m.raise_for_status = MagicMock()
    return m


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: no network, all HTTP mocked
# ══════════════════════════════════════════════════════════════════════════════

class TestInit:
    """__init__() derives portal_name from domain when not supplied."""

    def test_portal_name_derived_from_url(self):
        api = SymbiotaAPI("https://mycoportal.org/portal")
        assert api.portal_name == "mycoportal"

    def test_portal_name_explicit_overrides_url(self):
        api = SymbiotaAPI("https://mycoportal.org/portal", "custom_name")
        assert api.portal_name == "custom_name"

    def test_base_strips_trailing_slash(self):
        api = SymbiotaAPI("https://mycoportal.org/portal/")
        assert api.base == "https://mycoportal.org/portal"

    def test_lichenportal_derived_name(self):
        api = SymbiotaAPI("https://lichenportal.org/portal")
        assert api.portal_name == "lichenportal"

    def test_cch2_derived_name(self):
        api = SymbiotaAPI("https://cch2.org/portal")
        assert api.portal_name == "cch2"


class TestEmptyRecord:
    """_empty_record() must produce a fully-keyed, all-empty dict."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")

    def test_has_all_columns(self):
        rec = self.api._empty_record()
        assert list(rec.keys()) == COLUMNS

    def test_all_values_empty_string(self):
        rec = self.api._empty_record()
        assert all(v == "" for v in rec.values())

    def test_returns_new_dict_each_call(self):
        r1 = self.api._empty_record()
        r2 = self.api._empty_record()
        r1["Kingdom"] = "Fungi"
        assert r2["Kingdom"] == "", "Mutating one record must not affect another"


class TestExtractTaxonomy:
    """_extract_taxonomy() maps kingdomName + rankid ranges to the 5 hierarchy fields."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")

    def test_extracts_all_fields(self):
        data = {
            "kingdomName": "Fungi",
            "classification": [
                {"rankid": 30,  "scientificName": "Basidiomycota"},
                {"rankid": 60,  "scientificName": "Agaricomycetes"},
                {"rankid": 140, "scientificName": "Amanitaceae"},
                {"rankid": 160, "scientificName": "Amanitinae"},
            ],
        }
        result = self.api._extract_taxonomy(data)
        assert result["Kingdom"]   == "Fungi"
        assert result["Phylum"]    == "Basidiomycota"
        assert result["Class"]     == "Agaricomycetes"
        assert result["Family"]    == "Amanitaceae"
        assert result["Subfamily"] == "Amanitinae"

    def test_missing_classification_returns_empty_strings(self):
        result = self.api._extract_taxonomy({"kingdomName": "Fungi"})
        assert result["Phylum"]    == ""
        assert result["Class"]     == ""
        assert result["Family"]    == ""
        assert result["Subfamily"] == ""

    def test_kingdom_falls_back_to_rankid_10(self):
        data = {
            "classification": [
                {"rankid": 10, "scientificName": "Plantae"},
                {"rankid": 30, "scientificName": "Tracheophyta"},
            ]
        }
        result = self.api._extract_taxonomy(data)
        assert result["Kingdom"] == "Plantae"

    def test_prefers_lower_rankid_within_range(self):
        # Both 60 (Class) and 70 (Subclass) fall in the Class range (50-75)
        data = {
            "kingdomName": "Fungi",
            "classification": [
                {"rankid": 60, "scientificName": "Agaricomycetes"},
                {"rankid": 70, "scientificName": "Agaricomycetidae"},
            ],
        }
        result = self.api._extract_taxonomy(data)
        assert result["Class"] == "Agaricomycetes"

    def test_empty_data_returns_all_empty(self):
        result = self.api._extract_taxonomy({})
        assert all(v == "" for v in result.values())


class TestSearch:
    """search() tries api/v2/taxonomy/search, then api/v2/taxonomy."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")

    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_returns_result_from_first_endpoint(self, mock_get):
        mock_get.return_value = _mock_resp(_MOCK_SEARCH_RESULTS)
        result = self.api.search("Amanita muscaria")
        assert result == _MOCK_SEARCH_RESULTS
        first_url = mock_get.call_args_list[0][0][0]
        assert "taxonomy/search" in first_url

    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_falls_back_to_second_endpoint_when_first_fails(self, mock_get):
        # First call (taxonomy/search) → non-ok; second (taxonomy) → ok
        mock_get.side_effect = [
            _mock_resp(status=404),
            _mock_resp(_MOCK_SEARCH_RESULTS),
        ]
        result = self.api.search("Amanita muscaria")
        assert result == _MOCK_SEARCH_RESULTS
        urls = [c[0][0] for c in mock_get.call_args_list]
        assert any("taxonomy/search" in u for u in urls)
        assert any("taxonomy" in u and "search" not in u for u in urls)

    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_raises_when_both_endpoints_fail(self, mock_get):
        mock_get.side_effect = Exception("network error")
        with pytest.raises(RuntimeError):
            self.api.search("Amanita muscaria")

    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_wraps_list_response_in_results_key(self, mock_get):
        mock_get.return_value = _mock_resp([{"tid": 1, "sciname": "Amanita muscaria"}])
        result = self.api.search("Amanita muscaria")
        assert "results" in result
        assert isinstance(result["results"], list)

    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_passes_exact_query_params(self, mock_get):
        mock_get.return_value = _mock_resp(_MOCK_SEARCH_RESULTS)
        self.api.search("Amanita muscaria")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["taxon"] == "Amanita muscaria"
        assert params["type"] == "EXACT"
        assert params["limit"] == 100
        assert params["offset"] == 0


class TestGetTid:
    """_get_tid() extracts the tid from search() results; falls back to autocomplete."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")

    @patch.object(SymbiotaAPI, "search")
    def test_returns_tid_for_exact_match(self, mock_search):
        mock_search.return_value = _MOCK_SEARCH_RESULTS
        assert self.api._get_tid("Amanita muscaria") == 95084

    @patch.object(SymbiotaAPI, "search")
    def test_raises_when_search_has_no_match(self, mock_search):
        mock_search.return_value = {"results": []}
        with patch("scripts.APIs_pipe.symbiota.requests.get", side_effect=Exception):
            with pytest.raises(LookupError):
                self.api._get_tid("Aaaa bbbb")

    @patch.object(SymbiotaAPI, "search")
    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_falls_back_to_autocomplete_when_search_returns_no_match(
        self, mock_get, mock_search
    ):
        mock_search.return_value = {"results": []}
        mock_get.return_value = _mock_resp(
            [{"label": "Amanita muscaria (L.) Lam.", "id": "95084"}]
        )
        assert self.api._get_tid("Amanita muscaria") == 95084

    @patch.object(SymbiotaAPI, "search")
    def test_raises_when_both_lookups_fail(self, mock_search):
        mock_search.return_value = {"results": []}
        with patch("scripts.APIs_pipe.symbiota.requests.get", side_effect=Exception):
            with pytest.raises(LookupError):
                self.api._get_tid("Amanita muscaria")

    @patch.object(SymbiotaAPI, "search")
    @patch("scripts.APIs_pipe.symbiota.requests.get")
    def test_does_not_match_partial_name(self, mock_get, mock_search):
        # "Amanita" alone must not match "Amanita muscaria"; fallback also mocked
        # so no real HTTP call is made after the regex correctly rejects the result.
        mock_search.return_value = {
            "results": [{"tid": 95084, "sciname": "Amanita muscaria"}]
        }
        mock_get.return_value = _mock_resp([])
        with pytest.raises(LookupError):
            self.api._get_tid("Amanita")


class TestResolveAcceptedTid:
    """_resolve_accepted_tid() returns (accepted_tid, meta) for both accepted and synonym cases."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")

    @patch.object(SymbiotaAPI, "_get")
    def test_accepted_name_returns_same_tid(self, mock_get):
        mock_get.return_value = _mock_resp(_MOCK_TAXONOMY_ACCEPTED)
        accepted_tid, meta = self.api._resolve_accepted_tid(95084)
        assert accepted_tid == 95084
        assert meta["status"] == "Accepted"
        assert meta["accepted_name"] is None

    @patch.object(SymbiotaAPI, "_get")
    def test_accepted_name_taxonomy_fields_populated(self, mock_get):
        mock_get.return_value = _mock_resp(_MOCK_TAXONOMY_ACCEPTED)
        _, meta = self.api._resolve_accepted_tid(95084)
        assert meta["Kingdom"] == "Fungi"
        assert meta["Phylum"]  == "Basidiomycota"
        assert meta["Class"]   == "Agaricomycetes"
        assert meta["Family"]  == "Amanitaceae"

    @patch.object(SymbiotaAPI, "_get")
    def test_synonym_returns_accepted_tid(self, mock_get):
        # First call → synonym record; second call → accepted record
        mock_get.side_effect = [
            _mock_resp(_MOCK_TAXONOMY_SYNONYM),
            _mock_resp(_MOCK_TAXONOMY_ACCEPTED),
        ]
        accepted_tid, meta = self.api._resolve_accepted_tid(51234)
        assert accepted_tid == 95084
        assert meta["status"] == "Synonym"
        assert meta["accepted_name"] == "Amanita muscaria"

    @patch.object(SymbiotaAPI, "_get")
    def test_synonym_makes_second_call_for_accepted_taxonomy(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(_MOCK_TAXONOMY_SYNONYM),
            _mock_resp(_MOCK_TAXONOMY_ACCEPTED),
        ]
        self.api._resolve_accepted_tid(51234)
        assert mock_get.call_count == 2

    @patch.object(SymbiotaAPI, "_get")
    def test_synonym_captures_accepted_author(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(_MOCK_TAXONOMY_SYNONYM),
            _mock_resp(_MOCK_TAXONOMY_ACCEPTED),
        ]
        _, meta = self.api._resolve_accepted_tid(51234)
        assert meta["accepted_author"] == "(L.) Lam."

    @patch.object(SymbiotaAPI, "_get")
    def test_synonym_falls_back_to_own_classification_if_second_call_fails(
        self, mock_get
    ):
        mock_get.side_effect = [
            _mock_resp(_MOCK_TAXONOMY_SYNONYM),
            Exception("network error"),
        ]
        _, meta = self.api._resolve_accepted_tid(51234)
        # Falls back to the synonym's own classification; Fungi is still present
        assert meta["Kingdom"] == "Fungi"


class TestScrapeSynonyms:
    """_scrape_synonyms() parses synonymDiv HTML and produces full-schema records."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")
        self.taxonomy = {
            "Kingdom": "Fungi", "Phylum": "Basidiomycota",
            "Class": "Agaricomycetes", "Family": "Amanitaceae", "Subfamily": "",
        }

    @patch.object(SymbiotaAPI, "_get")
    def test_returns_list_of_dicts(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    @patch.object(SymbiotaAPI, "_get")
    def test_each_record_has_all_columns(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        for rec in result:
            assert list(rec.keys()) == COLUMNS

    @patch.object(SymbiotaAPI, "_get")
    def test_filters_infraspecific_taxa(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        names = [f"{r['Genus']} {r['Species']}" for r in result]
        # "Amanita muscaria var. flavivolvata" must be excluded
        assert all("var." not in n for n in names)

    @patch.object(SymbiotaAPI, "_get")
    def test_extracts_tid_from_href_links(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        tids = [r["Source Species ID"] for r in result]
        assert "51234" in tids
        assert "51235" in tids

    @patch.object(SymbiotaAPI, "_get")
    def test_source_link_uses_individual_tid(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        for rec in result:
            if rec["Source Species ID"]:
                assert rec["Source Species ID"] in rec["Source Link"]

    @patch.object(SymbiotaAPI, "_get")
    def test_inherits_taxonomy_from_accepted_taxon(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        for rec in result:
            assert rec["Kingdom"] == "Fungi"
            assert rec["Family"]  == "Amanitaceae"

    @patch.object(SymbiotaAPI, "_get")
    def test_gbif_accepted_status_is_synonym(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_SYNONYMDIV)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        assert all(r["GBIF Accepted Status"] == "Synonym" for r in result)

    @patch.object(SymbiotaAPI, "_get")
    def test_no_tid_links_results_in_empty_source_id(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_NO_TID_LINKS)
        result = self.api._scrape_synonyms(95084, self.taxonomy)
        assert len(result) == 1
        assert result[0]["Source Species ID"] == ""

    @patch.object(SymbiotaAPI, "_get")
    def test_empty_synonym_div_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_EMPTY_DIV)
        assert self.api._scrape_synonyms(95084, self.taxonomy) == []

    @patch.object(SymbiotaAPI, "_get")
    def test_no_synonym_div_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_resp(text=_MOCK_HTML_NO_DIV)
        assert self.api._scrape_synonyms(95084, self.taxonomy) == []


class TestSynonyms:
    """synonyms() orchestrates the pipeline and returns a correctly structured DataFrame."""

    def setup_method(self):
        self.api = SymbiotaAPI("https://mycoportal.org/portal")
        self._taxonomy = {
            "Kingdom": "Fungi", "Phylum": "Basidiomycota",
            "Class": "Agaricomycetes", "Family": "Amanitaceae", "Subfamily": "",
        }
        self._meta_accepted = {
            **self._taxonomy,
            "sciname": "Amanita muscaria", "author": "(L.) Lam.",
            "status": "Accepted", "accepted_tid": 95084, "accepted_name": None,
            "accepted_author": None,
        }
        self._meta_synonym = {
            **self._taxonomy,
            "sciname": "Agaricus muscarius", "author": "L.",
            "status": "Synonym", "accepted_tid": 95084,
            "accepted_name": "Amanita muscaria",
            "accepted_author": "(L.) Lam.",
        }
        self._scraped = [
            {
                **{col: "" for col in COLUMNS},
                **self._taxonomy,
                "Source Name": "mycoportal",
                "Genus": "Agaricus", "Species": "muscarius",
                "Source Species ID": "51234", "Author": "L.",
                "Source Link": "https://mycoportal.org/portal/taxa/index.php?taxon=51234",
                "GBIF Accepted Status": "Synonym",
            }
        ]

    def test_empty_string_returns_empty_dataframe(self):
        df = self.api.synonyms("")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == COLUMNS
        assert len(df) == 0

    def test_whitespace_string_returns_empty_dataframe(self):
        df = self.api.synonyms("   ")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @patch.object(SymbiotaAPI, "_get_tid", side_effect=LookupError("no taxon ID found"))
    def test_unknown_species_returns_empty_dataframe(self, _):
        df = self.api.synonyms("Aaaa bbbb")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == COLUMNS
        assert len(df) == 0

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_returns_dataframe(self, _, mock_resolve, mock_scrape):
        mock_resolve.return_value = (95084, self._meta_accepted)
        mock_scrape.return_value = []
        df = self.api.synonyms("Amanita muscaria")
        assert isinstance(df, pd.DataFrame)

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_has_exactly_columns(self, _, mock_resolve, mock_scrape):
        mock_resolve.return_value = (95084, self._meta_accepted)
        mock_scrape.return_value = []
        df = self.api.synonyms("Amanita muscaria")
        assert list(df.columns) == COLUMNS

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_first_row_is_queried_name(self, _, mock_resolve, mock_scrape):
        mock_resolve.return_value = (95084, self._meta_accepted)
        mock_scrape.return_value = self._scraped
        df = self.api.synonyms("Amanita muscaria")
        assert df.iloc[0]["Genus"] == "Amanita"
        assert df.iloc[0]["Species"] == "muscaria"

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=51234)
    def test_synonym_query_inserts_accepted_name_as_second_row(
        self, _, mock_resolve, mock_scrape
    ):
        mock_resolve.return_value = (95084, self._meta_synonym)
        mock_scrape.return_value = []
        df = self.api.synonyms("Agaricus muscarius")
        assert len(df) == 2
        assert df.iloc[0]["Genus"] == "Agaricus"   # queried synonym
        assert df.iloc[1]["Genus"] == "Amanita"    # accepted name

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=51234)
    def test_synonym_query_accepted_row_has_author(
        self, _, mock_resolve, mock_scrape
    ):
        mock_resolve.return_value = (95084, self._meta_synonym)
        mock_scrape.return_value = []
        df = self.api.synonyms("Agaricus muscarius")
        assert df.iloc[1]["Author"] == "(L.) Lam."

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_no_duplicate_canonical_names(self, _, mock_resolve, mock_scrape):
        mock_resolve.return_value = (95084, self._meta_accepted)
        # Scrape returns the queried name again; it must be deduplicated
        duplicate = {**self._scraped[0], "Genus": "Amanita", "Species": "muscaria"}
        mock_scrape.return_value = [duplicate]
        df = self.api.synonyms("Amanita muscaria")
        canonicals = (df["Genus"] + " " + df["Species"]).tolist()
        assert len(canonicals) == len(set(canonicals))

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_source_name_matches_portal(self, _, mock_resolve, mock_scrape):
        mock_resolve.return_value = (95084, self._meta_accepted)
        mock_scrape.return_value = []
        df = self.api.synonyms("Amanita muscaria")
        assert (df["Source Name"] == "mycoportal").all()

    @patch.object(SymbiotaAPI, "_scrape_synonyms")
    @patch.object(SymbiotaAPI, "_resolve_accepted_tid")
    @patch.object(SymbiotaAPI, "_get_tid", return_value=95084)
    def test_queried_accepted_name_has_correct_status(
        self, _, mock_resolve, mock_scrape
    ):
        mock_resolve.return_value = (95084, self._meta_accepted)
        mock_scrape.return_value = []
        df = self.api.synonyms("Amanita muscaria")
        assert df.iloc[0]["GBIF Accepted Status"] == "Accepted"

    @patch.object(SymbiotaAPI, "_get_tid", side_effect=Exception("unexpected"))
    def test_exception_returns_empty_dataframe(self, _):
        df = self.api.synonyms("Amanita muscaria")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == COLUMNS
        assert len(df) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: real HTTP calls, skipped if network is unavailable
# ══════════════════════════════════════════════════════════════════════════════

_INFRASPECIFIC_RE = re.compile(
    r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.)",
    re.IGNORECASE,
)


def _assert_dataframe_contract(df: pd.DataFrame, portal_name: str, species: str):
    """
    Assert that a synonyms DataFrame satisfies the full output contract.

    Parameters
    ----------
    df : pandas.DataFrame
        Result from ``SymbiotaAPI.synonyms()``.
    portal_name : str
        Expected value in the ``Source Name`` column for every row.
    species : str
        Binomial name that was queried; expected as the first row.
    """
    assert isinstance(df, pd.DataFrame), "synonyms() must return a DataFrame"
    assert list(df.columns) == COLUMNS, "DataFrame columns must match COLUMNS exactly"
    assert len(df) >= 1, f"Expected at least 1 row for '{species}'"

    # First row is always the queried name
    assert df.iloc[0]["Genus"] == species.split()[0]
    assert df.iloc[0]["Species"] == species.split()[1]

    # Source Name
    assert (df["Source Name"] == portal_name).all(), \
        "Every row must carry the portal name in 'Source Name'"

    # No infraspecific names
    for _, row in df.iterrows():
        canonical = f"{row['Genus']} {row['Species']}"
        assert not _INFRASPECIFIC_RE.search(canonical), \
            f"Infraspecific name leaked into results: {canonical!r}"

    # No duplicate canonical names
    canonicals = (df["Genus"] + " " + df["Species"]).str.strip().tolist()
    assert len(canonicals) == len(set(c.lower() for c in canonicals)), \
        "Duplicate canonical names found"

    # GBIF Accepted Status is always one of the three valid values
    valid_statuses = {"Accepted", "Synonym", ""}
    assert set(df["GBIF Accepted Status"].unique()).issubset(valid_statuses), \
        f"Unexpected GBIF Accepted Status values: {df['GBIF Accepted Status'].unique()}"

    # Source Species ID is numeric when populated
    for sid in df["Source Species ID"]:
        if sid:
            assert sid.isdigit(), f"Source Species ID {sid!r} is not numeric"


@pytest.mark.integration
class TestMyCoPortalIntegration:
    """
    Real HTTP calls to MyCoPortal (uses api/v2/taxonomy/search path).
    Skipped automatically when the portal is unreachable.
    """

    PORTAL = "https://mycoportal.org/portal"
    PORTAL_NAME = "mycoportal"

    @pytest.fixture(scope="class")
    def api(self):
        return SymbiotaAPI(self.PORTAL)

    @pytest.fixture(scope="class")
    def df_accepted(self, api):
        try:
            return api.synonyms("Amanita muscaria")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"MyCoPortal unreachable: {e}")

    @pytest.fixture(scope="class")
    def df_synonym_query(self, api):
        try:
            return api.synonyms("Agaricus muscarius")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"MyCoPortal unreachable: {e}")

    def test_synonyms_returns_dataframe(self, df_accepted):
        assert isinstance(df_accepted, pd.DataFrame)

    def test_synonyms_has_correct_columns(self, df_accepted):
        assert list(df_accepted.columns) == COLUMNS

    def test_synonyms_dataframe_contract(self, df_accepted):
        _assert_dataframe_contract(df_accepted, self.PORTAL_NAME, "Amanita muscaria")

    def test_synonyms_has_multiple_rows(self, df_accepted):
        assert len(df_accepted) > 1, "Amanita muscaria is known to have synonyms"

    def test_synonym_query_resolves_to_accepted(self, df_synonym_query):
        statuses = df_synonym_query["GBIF Accepted Status"].tolist()
        assert "Accepted" in statuses, \
            "Querying a synonym must include the accepted name in results"

    def test_nonexistent_species_returns_empty_dataframe(self, api):
        try:
            df = api.synonyms("Aaaa bbbb")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"MyCoPortal unreachable: {e}")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == COLUMNS
        assert len(df) == 0

    def test_search_returns_non_none_for_known_species(self, api):
        try:
            result = api.search("Amanita muscaria")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"MyCoPortal unreachable: {e}")
        assert result is not None
        assert "results" in result


@pytest.mark.integration
class TestLichenPortalIntegration:
    """
    Real HTTP calls to Lichen Portal (uses api/v2/taxonomy path, not /search).
    Confirms that the second endpoint in the cascade is exercised.
    Skipped automatically when the portal is unreachable.
    """

    PORTAL = "https://lichenportal.org/portal"
    PORTAL_NAME = "lichenportal"

    @pytest.fixture(scope="class")
    def api(self):
        return SymbiotaAPI(self.PORTAL)

    @pytest.fixture(scope="class")
    def df_accepted(self, api):
        try:
            return api.synonyms("Cladonia rangiferina")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"Lichen Portal unreachable: {e}")

    def test_synonyms_returns_dataframe(self, df_accepted):
        assert isinstance(df_accepted, pd.DataFrame)

    def test_synonyms_has_correct_columns(self, df_accepted):
        assert list(df_accepted.columns) == COLUMNS

    def test_synonyms_dataframe_contract(self, df_accepted):
        _assert_dataframe_contract(df_accepted, self.PORTAL_NAME, "Cladonia rangiferina")

    def test_kingdom_is_fungi(self, df_accepted):
        assert (df_accepted["Kingdom"] == "Fungi").all()

    def test_nonexistent_species_returns_empty_dataframe(self, api):
        try:
            df = api.synonyms("Aaaa bbbb")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"Lichen Portal unreachable: {e}")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
