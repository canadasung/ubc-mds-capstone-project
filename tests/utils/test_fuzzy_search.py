# These are unit tests, they do not hit the real GBIF API.
# Instead, requests.get is replaced with a Mock() that returns controlled fake
# responses. This keeps tests fast and reliable when there is no network access,
# but it means these tests will not catch changes to the GBIF API response format.
# For that, integration tests against the real API would be needed.

import sys
import os
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.utils.fuzzy_search import fuzzy_search


def make_response(data):
    """Return a mock requests.Response that yields data from .json()."""
    mock = Mock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


class TestFuzzySearch:

    # 1. Exact match returns a string, not a list
    def test_exact_match_returns_string(self):
        match = make_response({
            "matchType": "EXACT",
            "species": "Amanita muscaria",
            "canonicalName": "Amanita muscaria",
        })
        with patch("scripts.utils.fuzzy_search.requests.get", return_value=match):
            result = fuzzy_search("Amanita muscaria")

        assert result == "Amanita muscaria"
        assert isinstance(result, str)

    # 2. suggest is never called on an exact match
    def test_exact_match_only_calls_match_endpoint(self):
        match = make_response({
            "matchType": "EXACT",
            "species": "Amanita muscaria",
            "canonicalName": "Amanita muscaria",
        })
        with patch("scripts.utils.fuzzy_search.requests.get", return_value=match) as mock_get:
            fuzzy_search("Amanita muscaria")

        assert mock_get.call_count == 1

    # 3. Misspelling returns a list of candidates
    def test_fuzzy_match_returns_list(self):
        match = make_response({
            "matchType": "FUZZY",
            "species": "Amanita muscaria",
            "canonicalName": "Amanita muscaria",
            "confidence": 93,
        })
        suggest = make_response([
            {"canonicalName": "Amanita muscaria"},
            {"canonicalName": "Amanita muscoides"},
        ])
        with patch("scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]):
            result = fuzzy_search("Amanita muscara")

        assert isinstance(result, list)
        assert "Amanita muscaria" in result

    # 4. Corrected name (not the misspelling) is passed to suggest
    def test_fuzzy_match_uses_corrected_name_for_suggest(self):
        match = make_response({
            "matchType": "FUZZY",
            "species": "Amanita muscaria",
            "canonicalName": "Amanita muscaria",
            "confidence": 93,
        })
        suggest = make_response([])
        with patch("scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]) as mock_get:
            fuzzy_search("Amanita muscara")

        suggest_call_params = mock_get.call_args_list[1][1]["params"]
        assert suggest_call_params["q"] == "Amanita muscaria"

    # 5. Nonsense query returns an empty list
    def test_no_match_returns_empty_list(self):
        match = make_response({"matchType": "NONE"})
        suggest = make_response([])
        with patch("scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]):
            result = fuzzy_search("completelymadeupname")

        assert result == []

    # 6. Duplicate names from suggest are removed
    def test_suggestions_are_deduplicated(self):
        match = make_response({
            "matchType": "FUZZY",
            "species": "Amanita muscaria",
            "canonicalName": "Amanita muscaria",
        })
        suggest = make_response([
            {"canonicalName": "Amanita muscaria"},
            {"canonicalName": "Amanita muscaria"},  # duplicate
            {"canonicalName": "Amanita muscoides"},
        ])
        with patch("scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]):
            result = fuzzy_search("Amanita musc")

        assert result.count("Amanita muscaria") == 1

    # 7. Never returns more than 10 results
    def test_suggestions_capped_at_ten(self):
        match = make_response({"matchType": "NONE"})
        suggest = make_response([{"canonicalName": f"Species {i}"} for i in range(15)])
        with patch("scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]):
            result = fuzzy_search("Species")

        assert len(result) <= 10

    # 8. Genus-level match uses canonicalName when species field is None
    def test_falls_back_to_canonical_name_when_species_is_none(self):
        match = make_response({
            "matchType": "EXACT",
            "species": None,
            "canonicalName": "Amanita",
        })
        with patch("scripts.utils.fuzzy_search.requests.get", return_value=match):
            result = fuzzy_search("Amanita")

        assert result == "Amanita"
