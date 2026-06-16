"""
test_call_apis.py — Unit tests for call_apis.

All API functions are mocked; no network calls are made.

Run from the home directory:
    pytest tests/utils/test_call_apis.py -v
"""

import json
import typing
from unittest.mock import patch

import pytest

from deprecated.call_APIs import Source, call_apis

_PATCH_BASE = "scripts.utils.call_APIs"
_MOCK_RESULT = {"Species name": [], "Synonym name": []}


class TestSourcesNone:
    def test_returns_empty_json(self):
        """sources=None must return an empty JSON object."""
        assert json.loads(call_apis("Amanita muscaria", sources=None)) == {}


class TestSourceRouting:
    """Each source key must route to the correct underlying API function."""

    # Add an entry here when a new source is added to call_apis such that every possible source is covered by the tests in this class. If a new source is added to call_apis but not added here, test_all_source_literals_are_tested will fail and alert to the missing test coverage.
    _SOURCE_TO_FN: dict[str, str] = {
        "gbif": "get_gbif_synonyms",
        "genbank": "get_genbank_synonyms",
        "mushroomobs": "get_mushroom_observer_synonyms",
        "mycoportal": "get_mycoportal_synonyms",
        "bryophyteportal": "get_bryophyteportal_synonyms",
        "macroalgae": "get_macroalgae_synonyms",
        "indexfungorum": "get_indexfungorum_synonyms",
        "col": "get_checklistbank_synonyms",
    }

    def test_all_source_literals_are_tested(self):
        """Every value in the Source Literal must have an entry in _SOURCE_TO_FN.

        If this fails, a new source was added to call_APIs.Source but
        _SOURCE_TO_FN in test_call_apis.py was not updated.
        """
        known_sources = set(typing.get_args(Source))
        missing = known_sources - set(self._SOURCE_TO_FN)
        assert not missing, (
            f"Sources {missing} are defined in call_APIs.Source but not covered by "
            f"TestSourceRouting. Add new sources to _SOURCE_TO_FN in tests/utils/test_call_apis.py."
        )

    @pytest.mark.parametrize("source,fn_name", _SOURCE_TO_FN.items())
    def test_source_calls_correct_function(self, source, fn_name):
        """Each source key must call the correct API function with the query string."""
        with patch(f"{_PATCH_BASE}.{fn_name}", return_value=_MOCK_RESULT) as mock_fn:
            result = call_apis("Amanita muscaria", sources=[source])
            mock_fn.assert_called_once_with("Amanita muscaria")
            assert json.loads(result)[source] == _MOCK_RESULT


class TestReturnShape:
    def test_multiple_sources_all_present(self):
        """All requested sources must appear as keys in the returned JSON."""
        with (
            patch(f"{_PATCH_BASE}.get_gbif_synonyms", return_value=_MOCK_RESULT),
            patch(f"{_PATCH_BASE}.get_genbank_synonyms", return_value=_MOCK_RESULT),
        ):
            result = json.loads(
                call_apis("Amanita muscaria", sources=["gbif", "genbank"])
            )
            assert "gbif" in result
            assert "genbank" in result

    def test_only_requested_sources_in_result(self):
        """Only exactly the requested sources appear in the result."""
        with patch(f"{_PATCH_BASE}.get_gbif_synonyms", return_value=_MOCK_RESULT):
            result = json.loads(call_apis("Amanita muscaria", sources=["gbif"]))
            assert list(result.keys()) == ["gbif"]

    def test_returns_valid_json_string(self):
        """Return value must always be a parseable JSON string."""
        with patch(f"{_PATCH_BASE}.get_gbif_synonyms", return_value=_MOCK_RESULT):
            result = call_apis("Amanita muscaria", sources=["gbif"])
            assert isinstance(result, str)
            json.loads(result)


class TestErrorHandling:
    def test_unknown_source_returns_error_string(self):
        """An unrecognised source key must produce an error string in the result, not raise."""
        result = json.loads(call_apis("Amanita muscaria", sources=["unknown_source"]))
        assert "unknown_source" in result
        assert "Unknown source" in result["unknown_source"]

    def test_api_exception_returns_error_string(self):
        """An API call that raises must not crash — the error must be stored as a string."""
        with patch(
            f"{_PATCH_BASE}.get_gbif_synonyms", side_effect=Exception("timeout")
        ):
            result = json.loads(call_apis("Amanita muscaria", sources=["gbif"]))
            assert "Error" in result["gbif"]

    def test_one_failure_does_not_affect_other_sources(self):
        """A failing source must not prevent the remaining sources from being queried."""
        with (
            patch(f"{_PATCH_BASE}.get_gbif_synonyms", side_effect=Exception("timeout")),
            patch(f"{_PATCH_BASE}.get_genbank_synonyms", return_value=_MOCK_RESULT),
        ):
            result = json.loads(
                call_apis("Amanita muscaria", sources=["gbif", "genbank"])
            )
            assert "Error" in result["gbif"]
            assert result["genbank"] == _MOCK_RESULT
