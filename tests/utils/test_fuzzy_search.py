"""
test_fuzzy_search.py — Unit tests for scripts/utils/fuzzy_search.py.

requests.get is replaced with a Mock() that returns controlled fake responses.
This keeps tests fast and reliable without network access, but will not catch
changes to the GBIF API response format. See test_API_online.py for live
connectivity checks.

Run from the project root:
    pytest tests/utils/test_fuzzy_search.py -v
"""

from unittest.mock import Mock, patch

from scripts.utils.fuzzy_search import fuzzy_search


def make_response(data):
    """Return a mock requests.Response that yields data from .json()."""
    mock = Mock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


class TestFuzzySearch:
    # 1. Exact match returns a single-item list
    def test_exact_match_returns_list(self):
        match = make_response(
            {
                "matchType": "EXACT",
                "rank": "SPECIES",
                "species": "Amanita muscaria",
                "canonicalName": "Amanita muscaria",
            }
        )
        with patch("scripts.utils.fuzzy_search.requests.get", return_value=match):
            result = fuzzy_search("Amanita muscaria")

        assert result == ["Amanita muscaria"]
        assert isinstance(result, list)

    # 2. suggest is never called on an exact match
    def test_exact_match_only_calls_match_endpoint(self):
        match = make_response(
            {
                "matchType": "EXACT",
                "rank": "SPECIES",
                "species": "Amanita muscaria",
                "canonicalName": "Amanita muscaria",
            }
        )
        with patch(
            "scripts.utils.fuzzy_search.requests.get", return_value=match
        ) as mock_get:
            fuzzy_search("Amanita muscaria")

        assert mock_get.call_count == 1

    # 3. Misspelling returns a single-item list with the corrected name
    def test_fuzzy_match_returns_list(self):
        match = make_response(
            {
                "matchType": "FUZZY",
                "species": "Amanita muscaria",
                "canonicalName": "Amanita muscaria",
                "confidence": 93,
            }
        )
        with patch("scripts.utils.fuzzy_search.requests.get", return_value=match):
            result = fuzzy_search("Amanita muscara")

        assert result == ["Amanita muscaria"]
        assert isinstance(result, list)

    # 4. EXACT match at genus (or any non-species) rank falls through to suggest
    def test_exact_match_non_species_rank_falls_through_to_suggest(self):
        match = make_response(
            {
                "matchType": "EXACT",
                "rank": "GENUS",
                "canonicalName": "Amanita",
            }
        )
        suggest = make_response([{"canonicalName": "Amanita muscaria"}])
        with patch(
            "scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]
        ) as mock_get:
            result = fuzzy_search("Amanita")

        assert mock_get.call_count == 2
        assert result == ["Amanita muscaria"]

    # 5. FUZZY makes only one API call (no suggest)
    def test_fuzzy_match_only_calls_match_endpoint(self):
        match = make_response(
            {
                "matchType": "FUZZY",
                "species": "Amanita muscaria",
                "canonicalName": "Amanita muscaria",
            }
        )
        with patch(
            "scripts.utils.fuzzy_search.requests.get", return_value=match
        ) as mock_get:
            fuzzy_search("Amanita muscara")

        assert mock_get.call_count == 1

    # 6. Suggest entries with null canonicalName are filtered out
    def test_suggest_entries_with_null_canonical_name_are_filtered(self):
        match = make_response({"matchType": "NONE"})
        suggest = make_response(
            [
                {"canonicalName": None},
                {"canonicalName": "Amanita muscaria"},
            ]
        )
        with patch(
            "scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]
        ):
            result = fuzzy_search("Amanita")

        assert result == ["Amanita muscaria"]

    # 7. Nonsense query returns an empty list
    def test_no_match_returns_empty_list(self):
        match = make_response({"matchType": "NONE"})
        suggest = make_response([])
        with patch(
            "scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]
        ):
            result = fuzzy_search("completelymadeupname")

        assert result == []

    # 9. Duplicate names from suggest are removed
    def test_suggestions_are_deduplicated(self):
        match = make_response({"matchType": "NONE"})
        suggest = make_response(
            [
                {"canonicalName": "Amanita muscaria"},
                {"canonicalName": "Amanita muscaria"},  # duplicate
                {"canonicalName": "Amanita muscoides"},
            ]
        )
        with patch(
            "scripts.utils.fuzzy_search.requests.get", side_effect=[match, suggest]
        ):
            result = fuzzy_search("Amanita musc")

        assert result.count("Amanita muscaria") == 1
